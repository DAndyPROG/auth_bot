import json
import asyncio

from aiogram import Router, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from utils.auth import auth0_client
from utils.session import session_manager
from utils.database import db, User, Chat, Message as MessageModel
from handlers.states import UserForm

# Configuration of the router
router = Router()


# States for FSM
class AuthStates(StatesGroup):
    waiting_for_auth = State()
    authorized = State()
    waiting_for_user_data = State()


async def check_auth_status(message: Message, state: FSMContext, user_id: int, chat_id: int):
    """
    Checks the status of the user's authorization
    
    Args:
        message: Message from the user
        state: FSM state
        user_id: Telegram user ID
        chat_id: Telegram chat ID
    """
    max_attempts = 30  # Maximum number of attempts (30 * 5 seconds = 150 seconds)
    attempt = 0
    
    try:
        # Send the initial message about waiting
        status_message = await message.answer("⏳ waiting for authorization completion... (0%)")
        
        while attempt < max_attempts:
            # Check the access token
            token = await auth0_client.poll_device_flow(user_id)
            
            if token:
                # Successfully received the token
                # Get the user data from Auth0
                user_data = await auth0_client.get_user_info(token)
                
                # Save the Auth0 user ID
                auth0_id = user_data.get("sub")
                
                # Get the email from the authorization data
                email = user_data.get("email", "")
                full_name = user_data.get("name", "")
                
                # Update the user in the database
                async with db.async_session() as session:
                    # First, save the authorization data
                    user = await User.create_or_update(
                        session, user_id, auth0_id, user_data, True,
                        email=email, full_name=full_name
                    )
                    
                    # Set authorization in the session manager
                    await session_manager.set_authorized(
                        user_id, session, auth0_id, user_data
                    )
                    
                    # Change the user's state to waiting for additional data
                    # IMPORTANT: Always request additional data for each new authorization
                    # Send JSON with user data
                    user_data_json = json.dumps(user_data, indent=2)
                    await message.answer(user_data_json)
                    
                    # Log the bot's response with JSON data
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id,
                        text=user_data_json, 
                        from_user=False
                    )
                    
                    # Update the status message
                    await status_message.edit_text("✅ Authorization successful! Fill in additional data.")
                    
                    # Send a message about successful authorization
                    response = (
                        f"✅ Authorization completed successfully!"
                    )
                    await message.answer(response)
                    
                    # Log the bot's response
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id,
                        text=response, 
                        from_user=False
                    )
                    
                    # Now always request the full name, regardless of whether it already exists
                    await state.set_state(UserForm.waiting_full_name)
                    
                    # Send a request to enter the full name
                    response = (
                        f"To continue, please enter your full name "
                        f"(surname, name, patronymic):"
                    )
                    await message.answer(response)
                    
                    # Log the bot's response
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id,
                        text=response, 
                        from_user=False
                    )
                    
                    return
            
            # Increase the attempt counter
            attempt += 1
            
            # Update the status message every 5 attempts
            if attempt % 5 == 0:
                progress = int((attempt / max_attempts) * 100)
                await status_message.edit_text(f"⏳ Waiting for authorization completion... ({progress}%)")
            
            # Delay before the next attempt
            await asyncio.sleep(5)
        
        # If the maximum number of attempts is reached, inform about the timeout
        await status_message.edit_text("⏱️ Time out waiting for authorization")
        
        async with db.async_session() as session:
            # Close the user's session
            await session_manager.close_session(user_id)
            
            # Reset the state
            await state.clear()
            
            response = (
                f"⏱️ Time out waiting for authorization.\n"
                f"Authorization was not completed. Session closed.\n"
                f"For a new attempt to authorize, use the command /start."
            )
            await message.answer(response)
            
            # Log the bot's response
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=response, 
                from_user=False
            )
            
    except Exception as e:
        # If an error occurs, inform the user
        async with db.async_session() as session:
            # Close the user's session
            await session_manager.close_session(user_id)
            
            # Reset the state
            await state.clear()
            
            response = (
                f"❌ Error during authorization: {str(e)}.\n"
                f"Authorization was not completed. Session closed.\n"
                f"For a new attempt to authorize, use the command /start."
            )
            try:
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
            except Exception as msg_error:
                print(f"Failed to send a message: {msg_error}")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """
    Handler for the /start command
    
    Args:
        message: Message from the user
        state: FSM state
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Get the database session
        async with db.async_session() as session:
            # Create or update the user
            user = await User.get_by_telegram_id(session, user_id)
            if not user:
                user = await User.create_or_update(session, user_id)
                
                # Create a new chat
                await Chat.create(session, user.id, chat_id)
            
            # IMPORTANT: moved logging the message after creating the chat
            # Now we are sure that the chat record already exists
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            # If the user was deactivated due to inactivity, you need to start a new authorization
            if user.auth0_id and not user.is_active:
                # Start a new session
                await session_manager.start_session(user_id, session)
                
                try:
                    # Start the authorization process again
                    verification_url, user_code, expires_in = (
                        await auth0_client.start_device_flow(user_id)
                    )
                    
                    # Change the user's state
                    await state.set_state(AuthStates.waiting_for_auth)
                    
                    # Send instructions for authorization
                    response = (
                        f"🔐 You need to go through a new authorization because your session was closed due to inactivity.\n\n"
                        f"🚨🔑Follow the link: {verification_url}\n"
                        f"⏱️ The code is valid for {expires_in} seconds.\n"
                        f"Waiting for your authorization⌛..."
                    )
                    await message.answer(response)
                    
                    # Log the bot's response
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id, 
                        text=response, 
                        from_user=False
                    )
                    
                    # Start the authorization check
                    asyncio.create_task(check_auth_status(message, state, user_id, chat_id))
                    return
                except Exception as e:
                    # If there is an authentication problem, inform about the error
                    response = (
                        f"❌ Error during authorization: {str(e)}.\n"
                        f"Make sure your Auth0 settings are correct."
                    )
                    await message.answer(response)
                    
                    # Log the bot's response
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id, 
                        text=response, 
                        from_user=False
                    )
                    return
            
            # If the user is already authorized, check if the session is active
            if user.auth0_id and user.is_active:
                # If the user is already authorized, but the session is not active, activate it
                if not session_manager.is_authorized(user_id):
                    await session_manager.set_authorized(
                        user_id, 
                        session, 
                        user.auth0_id, 
                        user.auth0_data
                    )
                    await state.set_state(AuthStates.authorized)
                    
                    # Send JSON with user data
                    user_data_json = json.dumps(user.auth0_data, indent=2)
                    await message.answer(user_data_json)
                    
                    # Логуємо відповідь бота з JSON даними
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id, 
                        text=user_data_json, 
                        from_user=False
                    )
                    
                    # Send a message about successful authorization
                    response = (
                        f"✅ You are already authorized!\n\n"
                        f"Now you can send messages, and I will repeat them.\n"
                        f"If you are inactive for 1 minute, the session will be closed."
                    )
                    await message.answer(response)
                    
                    # Log the bot's response
                    await MessageModel.log_message(
                        session, 
                        chat_id=chat_id, 
                        text=response, 
                        from_user=False
                    )
                    
                    return
            
            # For all other cases, start a new authorization
            # Start the user's session
            await session_manager.start_session(user_id, session)
            
            try:
                # Start the authorization process
                verification_url, user_code, expires_in = (
                    await auth0_client.start_device_flow(user_id)
                )
                
                # Змінюємо стан користувача
                await state.set_state(AuthStates.waiting_for_auth)
                
                # Send instructions for authorization
                response = (
                    f"🔐 Please authorize through Auth0.\n\n"
                    f"🚨🔑Follow the link: {verification_url}\n"
                    f"⏱️ The code is valid for {expires_in} seconds.\n"
                    f"Waiting for your authorization⌛..."
                )
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
                
                # Start the authorization check
                asyncio.create_task(check_auth_status(message, state, user_id, chat_id))
            except Exception as e:
                # If there is an authentication problem, inform about the error
                response = (
                    f"❌ Error during authorization: {str(e)}.\n"
                    f"Make sure your Auth0 settings are correct."
                )
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
    except Exception as e:
        # Handle any errors during the execution of the start command
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")


@router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext):
    """
    Handler for the /logout command
    
    Args:
        message: Message from the user
        state: FSM state
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        async with db.async_session() as session:
            # Check if the chat exists in the database
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalars().first()
            
            if not chat:
                # If the chat does not exist, create it
                user = await User.get_by_telegram_id(session, user_id)
                if user:
                    chat = await Chat.create(session, user.id, chat_id)
                else:
                    # If there is no user or chat, return instructions
                    await message.answer("Please start working with the command /start")
                    return
            
            # Log the message
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            # Deactivate the user in the database
            await User.deactivate(session, user_id)
            
            # Close the session
            await session_manager.close_session(user_id)
            
            # Скидаємо стан
            await state.clear()
            
            # Send a message
            response = (
                "You have successfully logged out of the system. "
                "For a new attempt to authorize, use the command /start."
            )
            await message.answer(response)
            
            # Log the bot's response
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=response, 
                from_user=False
            )
    except Exception as e:
        # Handle any errors during the execution of the logout command
        await message.answer(f"Error during logout: {str(e)}. Please try again.")


@router.message(StateFilter(AuthStates.waiting_for_auth))
async def process_waiting_message(message: Message):
    """
    Handles messages during authorization waiting
    
    Args:
        message: Message from the user
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        async with db.async_session() as session:
            # Log the message
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            # Respond
            response = "⏳ Please complete authorization before continuing. Waiting for your authorization..."
            await message.answer(response)
            
            # Log the bot's response
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=response, 
                from_user=False
            )
    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")


@router.message(StateFilter(AuthStates.authorized))
async def process_authorized_message(message: Message):
    """
    Handles messages from an authorized user
    
    Args:
        message: Message from the user
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        async with db.async_session() as session:
            # Check if the chat exists in the database
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalars().first()
            
            if not chat:
                # If the chat does not exist, create it
                user = await User.get_by_telegram_id(session, user_id)
                if user:
                    chat = await Chat.create(session, user.id, chat_id)
                else:
                    # If there is no user or chat, return instructions
                    await message.answer("Please start working with the command /start")
                    return
            
            # Check and register user activity
            is_active = await session_manager.register_activity(user_id, session)
            
            if not is_active:
                # If the session is closed, inform about it
                response = (
                    "⏱️ Your session was disconnected due to inactivity (1 minute).\n"
                    "For a new authorization, use the command /start."
                )
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
                return
            
            # Log the message
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            # Send the message back
            await message.answer(message.text)
            
            # Log the bot's response
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=False
            )
    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")


@router.message(StateFilter(UserForm.waiting_full_name))
async def process_full_name(message: Message, state: FSMContext):
    """
    Handles the input of a full name
    
    Args:
        message: Message from the user
        state: FSM state
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Get the text of the message
        full_name = message.text.strip()
        
        # Log the message
        async with db.async_session() as session:
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            # Check the validity of the full name
            if len(full_name.split()) < 2:
                response = "❌ Please enter your full name in the format: Surname Name Patronymic"
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
                return
            
            # Save the full name in the FSM context
            await state.update_data(full_name=full_name)
            
            # Update the user in the database
            user = await User.get_by_telegram_id(session, user_id)
            if user:
                await User.create_or_update(
                    session,
                    user_id,
                    user.auth0_id,
                    user.auth0_data,
                    True,
                    full_name=full_name,
                    email=user.email
                )
            
            # Go to entering the phone number
            await state.set_state(UserForm.waiting_phone)
            
            # Send a request for the phone number
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Send phone number", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            response = "Now, please enter or send your phone number:"
            await message.answer(response, reply_markup=keyboard)
            
            # Log the bot's response
            await MessageModel.log_message( 
                session, 
                chat_id=chat_id, 
                text=response, 
                from_user=False
            )
    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")


@router.message(StateFilter(UserForm.waiting_phone))
async def process_phone(message: Message, state: FSMContext):
    """
    Handles the input of a phone number
    
    Args:
        message: Message from the user
        state: FSM state
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Get the phone number (it can be in the text or in the contact object)
        phone_number = None
        if message.contact and message.contact.phone_number:
            phone_number = message.contact.phone_number
        elif message.text:
            phone_number = message.text.strip()
        
        # Log the message
        async with db.async_session() as session:
            # Write the message ID
            message_id = message.message_id if hasattr(message, "message_id") else None
            
            # Log the message
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=f"Phone number: {phone_number}" if phone_number else "Phone number not received", 
                from_user=True,
                message_id=message_id
            )
            
            if not phone_number:
                response = "❌ Unable to get the phone number. Please try again."
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
                return
            
            # Check the format of the phone number
            # Remove all non-numeric characters
            cleaned_phone = ''.join(filter(str.isdigit, phone_number))
            
            # Check the length (minimum 10 digits)
            if len(cleaned_phone) < 10:
                response = "❌ The phone number must contain at least 10 digits. Please try again."
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
                return
            
            # Save the phone number in the FSM context
            user_data = await state.get_data()
            full_name = user_data.get("full_name", "")
            
            # Update the user in the database
            user = await User.get_by_telegram_id(session, user_id)
            if user:
                await User.create_or_update(
                    session,
                    user_id,
                    user.auth0_id,
                    user.auth0_data,
                    True,
                    full_name=full_name,
                    phone_number=phone_number,
                    email=user.email
                )
            
            # Go to the confirmation state
            await state.set_state(UserForm.waiting_confirmation)
            
            # Form a message with the data for confirmation
            response = (
                f"📋 Your data:\n\n"
                f"Full name: {full_name}\n"
                f"Phone: {phone_number}\n"
                f"Email: {user.email if user and user.email else 'Not specified'}\n\n"
                f"Are the data correct? Enter 'yes' to confirm or 'no' to re-enter."
            )
            
            # Create a keyboard for confirmation
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Yes")],
                    [KeyboardButton(text="No")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(response, reply_markup=keyboard)
            
            # Log the bot's response
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=response, 
                from_user=False
            )
    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")


@router.message(StateFilter(UserForm.waiting_confirmation))
async def process_confirmation(message: Message, state: FSMContext):
    """
    Handles the confirmation of the data
    
    Args:
        message: Message from the user
        state: FSM state
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Get the text of the message
        answer = message.text.strip().lower()
        
        # Log the message
        async with db.async_session() as session:
            await MessageModel.log_message(
                session, 
                chat_id=chat_id, 
                text=message.text, 
                from_user=True,
                message_id=message.message_id
            )
            
            if answer in ["так", "да", "yes", "y"]:
                # The user confirmed the data
                user = await User.get_by_telegram_id(session, user_id)
                
                # Змінюємо стан користувача
                await state.set_state(AuthStates.authorized)
                
                # Send a message about successful registration
                response = (
                    f"✅ Thank you! Registration completed successfully.\n\n"
                    f"Now you can send messages, and I will repeat them.\n"
                    f"If you are inactive for 1 minute, the session will be closed."
                )
                
                await message.answer(response, reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True))
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
            elif answer in ["ні", "нет", "no", "n"]:
                # The user did not confirm the data, we return to entering the full name
                await state.set_state(UserForm.waiting_full_name)
                
                response = "Please enter your full name (surname, name, patronymic):"
                await message.answer(response, reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True))
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
            else:
                # Unknown answer
                response = "Please enter 'yes' to confirm or 'no' to re-enter the data."
                await message.answer(response)
                
                # Log the bot's response
                await MessageModel.log_message(
                    session, 
                    chat_id=chat_id, 
                    text=response, 
                    from_user=False
                )
    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}. Please try again later.")
