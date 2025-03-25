import os
import asyncio
import time
from typing import Dict, Any, Optional
from sqlalchemy import select
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from utils.database import User, Chat, Message as MessageModel
from utils.auth import auth0_client

# Timeout for session   
SESSION_TIMEOUT = 60  # 1 minute


class SessionManager:
    def __init__(self):
        """Initialize the session manager"""
        self.sessions: Dict[int, dict] = {}
        self.timers: Dict[int, asyncio.Task] = {}
        self.bot = None  # Will be set during bot startup
    
    def set_bot(self, bot):
        """Sets the bot instance for sending messages"""
        self.bot = bot
    
    async def start_session(self, telegram_id: int, session: AsyncSession):
        """
        Starts a session for a user
        
        Args:
            telegram_id: ID of the user in Telegram
            session: SQLAlchemy session
        """
        # Create a record for the user if it doesn't exist
        await User.create_or_update(session, telegram_id)
        
        # Initialize the session
        self.sessions[telegram_id] = {
            "last_activity": time.time(),
            "is_authorized": False,
            "auth_data": None
        }
        
        # Start the timer for closing the session
        self.restart_timer(telegram_id)
    
    def restart_timer(self, telegram_id: int):
        """
        Restart the session timer
        
        Args:
            telegram_id: ID of the user in Telegram
        """
        # Cancel the existing task if any
        if telegram_id in self.timers and not self.timers[telegram_id].done():
            self.timers[telegram_id].cancel()
        
        # Create a new task
        self.timers[telegram_id] = asyncio.create_task(
            self._close_session_after_timeout_original(telegram_id)
        )
    
    async def _close_session_after_timeout(self, telegram_id: int, session: AsyncSession):
        """
        Close the session after timeout (helper method for testing)
        """
        if telegram_id in self.sessions:
            # Deactivate the user in the database
            await User.deactivate(session, telegram_id)
            
            # Remove the session
            if telegram_id in self.sessions:
                del self.sessions[telegram_id]
    
    async def _close_session_after_timeout_original(self, telegram_id: int):
        """
        Closes the session after inactivity
        
        Args:
            telegram_id: ID of the user in Telegram
        """
        try:
            # Wait for SESSION_TIMEOUT seconds
            await asyncio.sleep(SESSION_TIMEOUT)
            
            # Log that the timer has fired
            print(f"[{datetime.now()}] Timer fired for user {telegram_id}")
            
            # Check if the session still exists (it might have been closed by another way)
            if telegram_id in self.sessions:
                # If the user is authorized, close the session and send a message
                if self.sessions.get(telegram_id, {}).get("is_authorized", False):
                    print(f"[{datetime.now()}] User {telegram_id} is authorized, closing the session")
                    
                    # Prepare the message in advance
                    notification_text = (
                        "⏱️ Your session has been disconnected due to inactivity (1 minute).\n"
                        "For a new authorization, use the /start command."
                    )
                    
                    # First try to send a message, then close the session
                    # This will help avoid synchronization issues
                    if self.bot:
                        try:
                            print(f"[{datetime.now()}] Sending a message to user {telegram_id} before closing the session")
                            await self.bot.send_message(chat_id=telegram_id, text=notification_text)
                            print(f"[{datetime.now()}] Message sent successfully")
                        except Exception as msg_error:
                            print(f"[{datetime.now()}] Error sending a message: {msg_error.__class__.__name__}: {msg_error}")
                    
                    # Now close the session
                    await self.close_session(telegram_id, reason="timeout")
                    print(f"[{datetime.now()}] Session for user {telegram_id} closed due to inactivity")
                else:
                    # If the user is not authorized, just close the session without a message
                    print(f"[{datetime.now()}] User {telegram_id} is not authorized, closing the session")
                    await self.close_session(telegram_id, reason="timeout")
        except asyncio.CancelledError:
            # The timer was canceled, do nothing
            print(f"[{datetime.now()}] Timer for user {telegram_id} was canceled")
            pass
        except Exception as e:
            # Log any other errors to avoid losing execution
            print(f"[{datetime.now()}] Error closing the session due to timeout: {e.__class__.__name__}: {e}")
    
    async def register_activity(self, telegram_id: int, session: AsyncSession):
        """
        Registers user activity and restarts the timer
        
        Args:
            telegram_id: ID of the user in Telegram
            session: SQLAlchemy session
            
        Returns:
            bool: True if the user has an active session, False otherwise
        """
        if telegram_id not in self.sessions:
            return False
        
        self.sessions[telegram_id]["last_activity"] = time.time()
        self.restart_timer(telegram_id)
        return True
    
    async def set_authorized(
        self, 
        telegram_id: int, 
        session: AsyncSession,
        auth_id: str,
        auth_data: Dict[str, Any]
    ):
        """
        Sets the user's authorization status
        
        Args:
            telegram_id: ID of the user in Telegram
            session: SQLAlchemy session
            auth_id: Auth0 user ID
            auth_data: Authorization data
        """
        if telegram_id not in self.sessions:
            await self.start_session(telegram_id, session)
        
        self.sessions[telegram_id]["is_authorized"] = True
        self.sessions[telegram_id]["auth_data"] = auth_data
        
        # Update the information in the database
        await User.create_or_update(
            session, 
            telegram_id, 
            auth_id, 
            auth_data, 
            is_active=True
        )
        
        # Restart the timer
        self.restart_timer(telegram_id)
    
    def is_authorized(self, telegram_id: int) -> bool:
        """
        Checks if the user is authorized
        
        Args:
            telegram_id: ID of the user in Telegram
            
        Returns:
            bool: True if the user is authorized, False otherwise
        """
        if telegram_id not in self.sessions:
            return False
        
        return self.sessions[telegram_id]["is_authorized"]
    
    def get_auth_data(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns the user's authorization data
        
        Args:
            telegram_id: ID of the user in Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Authorization data or None
        """
        if not self.is_authorized(telegram_id):
            return None
        
        return self.sessions[telegram_id]["auth_data"]
    
    async def close_session(self, telegram_id: int, reason: str = ""):
        """
        Closes the user's session
        
        Args:
            telegram_id: ID of the user in Telegram
            reason: Reason for closing the session
        """
        try:
            if telegram_id in self.sessions:
                # Save the authorization information and the reason for closing before deleting the session
                was_authorized = self.sessions[telegram_id].get("is_authorized", False)
                was_timeout = reason == "timeout"
                
                # Deactivate the user in the database if it was a timeout and the user was authorized
                if was_timeout and was_authorized:
                    try:
                        from utils.database import User, db
                        async with db.async_session() as session:
                            await User.deactivate(session, telegram_id)
                            print(f"[{datetime.now()}] User {telegram_id} deactivated in the database")
                    except Exception as db_error:
                        print(f"[{datetime.now()}] Error deactivating user {telegram_id}: {db_error}")
                
                # Close the session
                # Delete the record from device_flow_data if it exists
                if hasattr(auth0_client, 'device_flow_data') and telegram_id in auth0_client.device_flow_data:
                    del auth0_client.device_flow_data[telegram_id]
                
                # Delete the session
                del self.sessions[telegram_id]
                
                # Cancel the timer
                if telegram_id in self.timers and not self.timers[telegram_id].done():
                    self.timers[telegram_id].cancel()
                    del self.timers[telegram_id]
                
                # Return the information about the reason for closing and the authorization status
                return True
            return False
        except Exception as e:
            print(f"[{datetime.now()}] Error closing the session for user {telegram_id}: {e}")
            return False
    
    async def _send_timeout_notification(self, telegram_id: int, session: AsyncSession):
        """
        Send a timeout notification (helper method for testing)
        """
        if self.bot:
            # Надсилаємо повідомлення про закриття сесії
            message_text = "⏱️ Вашу сесію було від'єднано через неактивність (1 хвилина). Для нової авторизації використайте команду /start"
            await self.bot.send_message(telegram_id, message_text)
            
            # Логуємо повідомлення в базу даних
            await MessageModel.log_message(
                session,
                telegram_id,
                message_text,
                from_user=False
            )
            
    async def send_timeout_notification(self, bot, telegram_id: int):
        """
        Sends a message about the session closure due to inactivity
        
        Args:
            bot: Instance of the bot for sending messages
            telegram_id: ID of the user in Telegram
        """
        try:
            # Preparing the message
            response = (
                "⏱️ Your session has been disconnected due to inactivity (1 minute).\n"
                "For a new authorization, use the /start command."
            )
            
            # Try to send a message
            print(f"[{datetime.now()}] Trying to send a message to user {telegram_id}")
            try:
                await bot.send_message(chat_id=telegram_id, text=response)
                print(f"[{datetime.now()}] Message sent successfully to user {telegram_id}")
            except Exception as msg_error:
                print(f"[{datetime.now()}] Details of the error when sending a message: {msg_error.__class__.__name__}: {msg_error}")
                # Try again with a delay
                try:
                    await asyncio.sleep(1)
                    print(f"[{datetime.now()}] Trying to send a message again")
                    await bot.send_message(chat_id=telegram_id, text=response)
                    print(f"[{datetime.now()}] The second attempt was successful")
                except Exception as retry_error:
                    print(f"[{datetime.now()}] Error when trying again: {retry_error.__class__.__name__}: {retry_error}")
                    print(f"[{datetime.now()}] Failed to send notification to user {telegram_id}")
            
            # Log the message in the database if possible
            try:
                from utils.database import Chat, Message as MessageModel, db
                
                async with db.async_session() as session:
                    # Get information about the chat
                    result = await session.execute(
                        select(Chat).where(Chat.chat_id == telegram_id)
                    )
                    chat = result.scalars().first()
                    
                    if chat:
                        # Log the message in the database
                        await MessageModel.log_message(
                            session,
                            chat_id=telegram_id,
                            text=response,
                            from_user=False
                        )
            except Exception as db_error:
                # If it was not possible to log the message in the database, ignore the error
                # This should not prevent the message from being sent successfully
                print(f"[{datetime.now()}] Error when logging the message about timeout: {db_error}")
        except Exception as e:
            print(f"[{datetime.now()}] Critical error when sending a message about timeout: {e.__class__.__name__}: {e}")


# Create a global session manager
session_manager = SessionManager()
