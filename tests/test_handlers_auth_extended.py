import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from handlers.auth import (
    process_waiting_message, process_authorized_message, process_full_name,
    process_phone, process_confirmation, AuthStates, UserForm
)
from utils.database import User, Message as MessageModel, Chat

# Tests for process_waiting_message
@pytest.mark.asyncio
async def test_process_waiting_message(mock_message, async_session):
    """Test processing a message during authorization waiting"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_waiting_message(mock_message)
        
        # Check that the message was logged
        mock_log_message.assert_awaited_once_with(
            async_session, 
            chat_id=654321, 
            text="test message", 
            from_user=True,
            message_id=mock_message.message_id
        )
        
        # Check the response
        mock_message.answer.assert_awaited_once()
        assert "Please complete authorization" in mock_message.answer.call_args[0][0]
        
        # Check that the response was logged
        assert mock_log_message.await_count == 2

@pytest.mark.asyncio
async def test_process_waiting_message_error(mock_message):
    """Test processing an error during authorization waiting"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await process_waiting_message(mock_message)
        
        # Check that the error response was sent
        mock_message.answer.assert_awaited_once_with(
            "❌ An error occurred: Database error. Please try again later."
        )

# Tests for process_authorized_message
@pytest.mark.asyncio
async def test_process_authorized_message_active_session(mock_message, async_session):
    """Test processing a message from an authorized user with an active session"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.select') as mock_select, \
         patch('handlers.auth.session_manager.register_activity') as mock_register_activity, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for execute and query result
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_execute_result = AsyncMock()
        mock_execute_result.scalars.return_value.first.return_value = mock_chat
        async_session.execute.return_value = mock_execute_result
        
        # Мок для session_manager.register_activity
        mock_register_activity.return_value = True
        
        # Call the function
        await process_authorized_message(mock_message)
        
        # Check that the activity was registered
        mock_register_activity.assert_awaited_once_with(123456, async_session)
        
        # Check that the message was logged
        mock_log_message.assert_awaited()
        assert mock_log_message.await_count >= 2
        
        # Check the response
        mock_message.answer.assert_awaited_once_with("test message")

@pytest.mark.asyncio
async def test_process_authorized_message_inactive_session(mock_message, async_session):
    """Test processing a message from an authorized user with an inactive session"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.select') as mock_select, \
         patch('handlers.auth.session_manager.register_activity') as mock_register_activity, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for execute and query result
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_execute_result = AsyncMock()
        mock_execute_result.scalars.return_value.first.return_value = mock_chat
        async_session.execute.return_value = mock_execute_result
        
        # Мок для session_manager.register_activity
        mock_register_activity.return_value = False  # Сесія неактивна
        
        # Call the function
        await process_authorized_message(mock_message)
        
        # Check the response about the inactive session
        assert any("Your session was disconnected due to inactivity" in str(call) for call in mock_message.answer.call_args_list)
        
        # Check that the response was logged
        assert mock_log_message.await_count == 1

@pytest.mark.asyncio
async def test_process_authorized_message_no_chat(mock_message, async_session):
    """Test processing a message from an authorized user when the chat is not found"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.select') as mock_select, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.Chat.create') as mock_create_chat:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for execute and query result - chat not found
        mock_execute_result = AsyncMock()
        mock_execute_result.scalars.return_value.first.return_value = None
        async_session.execute.return_value = mock_execute_result

        # Mock for User.get_by_telegram_id - user not found
        mock_get_user.return_value = None
        
        # Call the function
        await process_authorized_message(mock_message)
        
        # Check the response
        mock_message.answer.assert_awaited_once_with("Please start working with the command /start")

@pytest.mark.asyncio
async def test_process_authorized_message_error(mock_message):
    """Test processing an error during processing a message from an authorized user"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "test message"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await process_authorized_message(mock_message)
        
        # Check that the error response was sent
        mock_message.answer.assert_awaited_once_with(
            "❌ An error occurred: Database error. Please try again later."
        )

# Тести для process_full_name
@pytest.mark.asyncio
async def test_process_full_name_valid(mock_message, mock_state, async_session):
    """Test processing a valid name"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "John Smith"

    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.User.create_or_update') as mock_create_user:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for User.get_by_telegram_id
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = "auth0|test123"
        mock_user.auth0_data = {"sub": "auth0|test123", "name": "Test User"}
        mock_user.email = "test@example.com"
        mock_get_user.return_value = mock_user
        
        # Call the function
        await process_full_name(mock_message, mock_state)
        
        # Check that the message was logged
        mock_log_message.assert_awaited_once_with(
            async_session, 
            chat_id=654321, 
            text="John Smith", 
            from_user=True,
            message_id=mock_message.message_id
        )
        
        # Check that the state was updated with the name
        mock_state.update_data.assert_awaited_once_with(full_name="John Smith")
        
        # Check that the user was updated in the database
        mock_create_user.assert_awaited_once()
        assert "John Smith" in mock_create_user.call_args[1]["full_name"]
        
        # Check that the state was changed to waiting_phone
        mock_state.set_state.assert_awaited_once_with(UserForm.waiting_phone)
        
        # Check the response with the keyboard
        mock_message.answer.assert_awaited_once()
        assert "phone number" in mock_message.answer.call_args[0][0].lower()
        assert "reply_markup" in mock_message.answer.call_args[1]

@pytest.mark.asyncio
async def test_process_full_name_invalid(mock_message, mock_state, async_session):
    """Test processing an invalid name (too short)"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "John"  # Only one word
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_full_name(mock_message, mock_state)
        
        # Check that the message was logged
        mock_log_message.assert_awaited()
        
        # Check the error response
        assert any("Please enter your full name in the format:" in str(call) for call in mock_message.answer.call_args_list)
        
        # Check that the state was not changed
        mock_state.set_state.assert_not_awaited()

@pytest.mark.asyncio
async def test_process_full_name_error(mock_message, mock_state):
    """Test processing an error during processing a name"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "John Smith"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await process_full_name(mock_message, mock_state)
        
        # Check that the error response was sent
        mock_message.answer.assert_awaited_once_with(
            "❌ An error occurred: Database error. Please try again later."
        )

# Тести для process_phone
@pytest.mark.asyncio
async def test_process_phone_from_text(mock_message, mock_state, async_session):
    """Test processing a phone number from a message text"""
    #Set theemockeobjects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "+380931234567"
    mock_message.contact = None  # Noncontactlyonlyttext
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.User.create_or_update') as mock_create_user:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for User.get_by_telegram_id
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = "auth0|test123"
        mock_user.auth0_data = {"sub": "auth0|test123", "name": "Test User"}
        mock_user.email = "test@example.com"
        mock_get_user.return_value = mock_user
        
        # Мок для state.get_data
        mock_state.get_data.return_value = {"full_name": "Іванов Іван Іванович"}
        
        # Call the function
        await process_phone(mock_message, mock_state)
        
        # Check that the message was logged
        mock_log_message.assert_awaited_once()
        
        # Check that the user was updated in the database
        mock_create_user.assert_awaited_once()
        assert "+380931234567" in mock_create_user.call_args[1]["phone_number"]
        
        # Check that the state was changed to waiting_confirmation
        mock_state.set_state.assert_awaited_once_with(UserForm.waiting_confirmation)
        
        # Check the response with the keyboard for confirmation
        mock_message.answer.assert_awaited_once()
        assert "Your data" in mock_message.answer.call_args[0][0]
        assert "reply_markup" in mock_message.answer.call_args[1]

@pytest.mark.asyncio
async def test_process_phone_from_contact(mock_message, mock_state, async_session):
    """Test processing a phone number from a contact"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = ""  # No text
    mock_message.contact = MagicMock()
    mock_message.contact.phone_number = "+380931234567"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.User.create_or_update') as mock_create_user:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for User.get_by_telegram_id
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = "auth0|test123"
        mock_user.auth0_data = {"sub": "auth0|test123", "name": "Test User"}
        mock_user.email = "test@example.com"
        mock_get_user.return_value = mock_user
        
        # Мок для state.get_data
        mock_state.get_data.return_value = {"full_name": "Іванов Іван Іванович"}
        
        # Call the function
        await process_phone(mock_message, mock_state)
        
        # Check that the message was logged
        mock_log_message.assert_awaited_once()
        
        # Check that the user was updated in the database
        mock_create_user.assert_awaited_once()
        assert "+380931234567" in mock_create_user.call_args[1]["phone_number"]
        
        # Check that the state was changed to waiting_confirmation
        mock_state.set_state.assert_awaited_once_with(UserForm.waiting_confirmation)

@pytest.mark.asyncio
async def test_process_phone_invalid(mock_message, mock_state, async_session):
    """Test processing an invalid phone number (too short)"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "12345"  # Short number
    mock_message.contact = None
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_phone(mock_message, mock_state)
        
        # Check the error response
        assert any("The phone number must contain at least 10 digits" in str(call) for call in mock_message.answer.call_args_list)
        
        # Check that the state was not changed
        mock_state.set_state.assert_not_awaited()

@pytest.mark.asyncio
async def test_process_phone_no_phone(mock_message, mock_state, async_session):
    """Test processing a missing phone number"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = None
    mock_message.contact = None
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_phone(mock_message, mock_state)
        
        # Check the error response
        assert any("Unable to get the phone number" in str(call) for call in mock_message.answer.call_args_list)
        
        # Check that the state was not changed
        mock_state.set_state.assert_not_awaited()

# Tests for process_confirmation
@pytest.mark.asyncio
async def test_process_confirmation_yes(mock_message, mock_state, async_session):
    """Test processing a confirmation (response "Yes")"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "Yes"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Мок для User.get_by_telegram_id
        mock_user = MagicMock()
        mock_get_user.return_value = mock_user
        
        # Call the function
        await process_confirmation(mock_message, mock_state)
        
        # Check that the message was logged
        mock_log_message.assert_awaited()
        
        # Check that the state was changed to authorized
        mock_state.set_state.assert_awaited_once_with(AuthStates.authorized)
        
        # Check the response without a keyboard
        mock_message.answer.assert_awaited_once()
        assert "Registration completed successfully" in mock_message.answer.call_args[0][0]
        assert "reply_markup" in mock_message.answer.call_args[1]

@pytest.mark.asyncio
async def test_process_confirmation_no(mock_message, mock_state, async_session):
    """Test processing a refusal to confirm data (response "No")"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "No"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_confirmation(mock_message, mock_state)
        
        # Check that the state was changed to waiting_full_name
        mock_state.set_state.assert_awaited_once_with(UserForm.waiting_full_name)
        
        # Check the response without a keyboard
        mock_message.answer.assert_awaited_once()
        assert "Please enter your full name" in mock_message.answer.call_args[0][0]
        assert "reply_markup" in mock_message.answer.call_args[1]

@pytest.mark.asyncio
async def test_process_confirmation_unknown(mock_message, mock_state, async_session):
    """Test processing an unknown response when confirming data"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "Maybe"  # Unknown response
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await process_confirmation(mock_message, mock_state)
        
        # Check the response with a request to give a clear answer
        mock_message.answer.assert_awaited_once_with("Please enter 'yes' to confirm or 'no' to re-enter the data.")
        
        # Check that the state was not changed
        mock_state.set_state.assert_not_awaited()

@pytest.mark.asyncio
async def test_process_confirmation_error(mock_message, mock_state):
    """Test processing an error when confirming data"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "Yes"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await process_confirmation(mock_message, mock_state)
        
        # Check that the error response was sent
        mock_message.answer.assert_awaited_once_with(
            "❌ An error occurred: Database error. Please try again later."
        ) 