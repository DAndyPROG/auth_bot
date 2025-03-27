import os
import datetime
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from utils.database import AsyncDatabase, Base, User, Chat, Message, db


class TestAsyncDatabase:
    @patch('utils.database.create_async_engine')
    def test_init_with_default_url(self, mock_create_engine):
        """Test initialization with the default URL"""
        # Set the environment variable for the test
        mock_create_engine.return_value = MagicMock()
        
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://postgres:postgress@db:5432/tgbot"}):
            db = AsyncDatabase()
            # Check that the create_async_engine method was called with the correct URL
            assert mock_create_engine.called
            args, kwargs = mock_create_engine.call_args
            assert args[0] == "postgresql+asyncpg://postgres:postgress@db:5432/tgbot" # type: ignore
    
    @patch('utils.database.create_async_engine')
    def test_init_with_custom_url(self, mock_create_engine):
        """Test initialization with a custom URL"""
        mock_create_engine.return_value = MagicMock()
        
        db = AsyncDatabase(url="custom_url")
        # Check that the create_async_engine method was called with the custom URL
        assert mock_create_engine.called
        args, kwargs = mock_create_engine.call_args
        assert args[0] == "custom_url" # type: ignore
    
    @pytest.mark.asyncio
    async def test_init_models(self):
        """Test initialization of database models"""
        # Create our mocks
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_metadata = MagicMock()
        
        # Patch the necessary components
        with patch('utils.database.create_async_engine', return_value=mock_engine), \
             patch('utils.database.async_sessionmaker'), \
             patch.object(mock_engine, 'begin', return_value=MagicMock(
                 __aenter__=AsyncMock(return_value=mock_connection),
                 __aexit__=AsyncMock())):
            
            # Create an instance of AsyncDatabase
            db = AsyncDatabase()
            
            # Call the method, check that it doesn't raise an error
            await db.init_models()
            
            # The init_models method ended without errors - the test is successful
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test the get_session method"""
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create an instance of the class and replace async_session with a mock
        db = AsyncDatabase()
        db.async_session = MagicMock()
        db.async_session.return_value.__aenter__.return_value = mock_session
        
        # Call the get_session method
        async with await db.get_session() as session:
            assert session == mock_session
    
    @pytest.mark.asyncio
    async def test_get_session_no_engine(self):
        """Test the error when the engine is not available"""
        # Create an instance of the class with engine=None
        db = AsyncDatabase()
        db.engine = None
        
        # Check that the correct error is raised
        with pytest.raises(Exception, match="Database engine is not available"):
            async with await db.get_session() as session:
                pass


class TestUser:
    @pytest.mark.asyncio
    async def test_get_by_telegram_id(self):
        """Test the get_by_telegram_id method of the User class"""
        # Create a mock for the session and execute
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        
        # Set the result for scalars().first()
        mock_user = MagicMock(spec=User)
        mock_result.scalars.return_value.first.return_value = mock_user
        
        # Call theemethod
        result = await User.get_by_telegram_id(mock_session, 123456)
        
        # Check the result
        assert result == mock_user
        # Check that the correct query was called
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_telegram_id_none(self):
        """Test the get_by_telegram_id method when the user is not found"""
        # Create a mock for the session and execute
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        
        # Set None as the result for scalars().first()
        mock_result.scalars.return_value.first.return_value = None
        
        # Call the method
        result = await User.get_by_telegram_id(mock_session, 123456)
        
        # Check the result
        assert result is None
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_create_or_update_new_user(self, mock_get_by_telegram_id):
        """Test creating a new user"""
        # Set the user to not exist
        mock_get_by_telegram_id.return_value = None
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method
        result = await User.create_or_update(
            mock_session, 
            123456, 
            "auth0|123", 
            {"sub": "auth0|123", "name": "Test User"},
            True,
            "Test User",
            "+123456789",
            "test@example.com"
        )
        
        # Check that a new user was created
        assert isinstance(result, User)
        assert result.telegram_id == 123456
        assert result.auth0_id == "auth0|123"
        assert result.is_active == True
        
        # Check that the user was added to the session and changes were saved
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_create_or_update_special_telegram_id(self, mock_get_by_telegram_id):
        """Test handling special values of telegram_id"""
        # Test the special case of telegram_id = 123001
        mock_get_by_telegram_id.return_value = None
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method with the value of is_active_override
        result = await User.create_or_update(
            mock_session, 
            123001,
            "auth0|123", 
            {"sub": "auth0|123", "name": "Test User"}
        )
        
        # Check that is_active was set to True
        assert result.is_active == True
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_create_or_update_existing_user(self, mock_get_by_telegram_id):
        """Test updating an existing user"""
        # Create a mock for the existing user
        existing_user = User(
            telegram_id=123456,
            auth0_id="old_auth0_id",
            is_active=False,
            full_name="Old Name",
            phone_number="",
            email=""
        )
        mock_get_by_telegram_id.return_value = existing_user
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method
        result = await User.create_or_update(
            mock_session, 
            123456, 
            "auth0|123", 
            {"sub": "auth0|123", "name": "New Name"},
            True,
            "New Full Name",
            "+123456789",
            "test@example.com"
        )
        
        # Check that the user was updated
        assert result == existing_user
        assert result.auth0_id == "auth0|123"
        assert result.is_active == True
        assert result.full_name == "New Full Name"
        assert result.phone_number == "+123456789"
        assert result.email == "test@example.com"
        
        # Check that commit was called to save changes
        mock_session.commit.assert_called_once()
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_create_or_update_with_auth0_data_extraction(self, mock_get_by_telegram_id):
        """Test extraction of data from auth0_data during user update"""
        # Set the user to not exist
        mock_get_by_telegram_id.return_value = None
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method only with auth0_data
        result = await User.create_or_update(
            mock_session, 
            123456, 
            "auth0|123", 
            {
                "sub": "auth0|123", 
                "name": "From Auth0", 
                "email": "auth0@example.com",
                "phone_number": "+111222333"
            }
        )
        
        # Check that the data was extracted from auth0_data
        assert result.full_name == "From Auth0"
        assert result.email == "auth0@example.com"
        assert result.phone_number == "+111222333"
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_deactivate_existing_user(self, mock_get_by_telegram_id):
        """Test deactivating an existing user"""
        # Create a mock for the existing user
        existing_user = User(
            telegram_id=123456,
            is_active=True
        )
        mock_get_by_telegram_id.return_value = existing_user
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method
        result = await User.deactivate(mock_session, 123456)
        
        # Check that the user was deactivated
        assert result == existing_user
        assert result.is_active == False
        
        # Check that commit was called to save changes
        mock_session.commit.assert_called_once()
    
    @patch.object(User, 'get_by_telegram_id')
    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_user(self, mock_get_by_telegram_id):
        """Test deactivating a non-existent user"""
        # Set the user to not exist
        mock_get_by_telegram_id.return_value = None
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method
        result = await User.deactivate(mock_session, 123456)
        
        # Check that the result is None
        assert result is None
        
        # Check that commit was not called
        mock_session.commit.assert_not_called()


class TestChat:
    @pytest.mark.asyncio
    async def test_create(self):
        """Test creating a new chat"""
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Call the method
        result = await Chat.create(mock_session, 1, 123456)
        
        # Check the result
        assert isinstance(result, Chat)
        assert result.user_id == 1
        assert result.chat_id == 123456
        
        # Check that the chat was added to the session and changes were saved
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_chats(self):
        """Test getting the user's chats"""
        # Create mocks for the chats
        mock_chat1 = MagicMock(spec=Chat)
        mock_chat2 = MagicMock(spec=Chat)
        
        # Create a mock for the session and execute
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        
        # Set the result for scalars().all()
        mock_result.scalars.return_value.all.return_value = [mock_chat1, mock_chat2]
        
        # Call the method
        result = await Chat.get_user_chats(mock_session, 1)
        
        # Check the result
        assert result == [mock_chat1, mock_chat2]
        
        # Check that the correct query was called
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id(self):
        """Test getting a chat by ID"""
        # Create a mock for the chat
        mock_chat = MagicMock(spec=Chat)
        
        # Create a mock for the session and execute
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        
        # Set the result for scalars().first()
        mock_result.scalars.return_value.first.return_value = mock_chat
        
        # Call the method
        result = await Chat.get_by_id(mock_session, 1)
        
        # Check the result
        assert result == mock_chat
        
        # Check that the correct query was called
        mock_session.execute.assert_called_once()


class TestMessage:
    @patch.object(Chat, 'get_by_id')
    @pytest.mark.asyncio
    async def test_log_message(self, mock_get_by_id):
        """Test logging a message"""
        # Create a mock for the chat
        mock_chat = MagicMock(spec=Chat)
        mock_chat.id = 1
        mock_get_by_id.return_value = mock_chat
        
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create a mock for execute and select to find the chat by chat_id
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.scalars.return_value.first.return_value = mock_chat
        
        # Call the method
        result = await Message.log_message(mock_session, 123456, "Test message", True, 1)
        
        # Check the result
        assert isinstance(result, Message)
        assert result.chat_id == 1
        assert result.text == "Test message"
        assert result.from_user == True
        assert result.message_id == 1
        
        # Check that the message was added to the session and changes were saved
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @patch.object(Chat, 'get_by_id')
    @pytest.mark.asyncio
    async def test_log_message_no_chat(self, mock_get_by_id):
        """Test the error when logging a message for a non-existent chat"""
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Set the result to None
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.scalars.return_value.first.return_value = None
        
        # Check that the correct error is raised
        with pytest.raises(Exception, match="Chat with ID 123456 not found"):
            await Message.log_message(mock_session, 123456, "Test message", True, 1)
    
    @pytest.mark.asyncio
    async def test_get_chat_history(self):
        """Test getting the chat history"""
        # Create mocks for the messages
        mock_message1 = MagicMock(spec=Message)
        mock_message2 = MagicMock(spec=Message)
        
        # Create a mock for the chat
        mock_chat = MagicMock(spec=Chat)
        mock_chat.id = 1
        
        # Create a mock for the session and execute
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create a mock for the first query (finding the chat)
        mock_chat_result = MagicMock()
        # Create a mock for the second query (message history)
        mock_message_result = MagicMock()
        
        # Set the result for the first query
        mock_session.execute.side_effect = [mock_chat_result, mock_message_result]
        
        # Set the result for the first query
        mock_chat_result.scalars.return_value.first.return_value = mock_chat
        
        # Set the result for the second query
        mock_message_result.scalars.return_value.all.return_value = [mock_message1, mock_message2]
        
        # Call the method
        result = await Message.get_chat_history(mock_session, 123456)
        
        # Check the result
        assert result == [mock_message1, mock_message2]
        
        # Check that execute was called twice
        assert mock_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_chat_history_no_chat(self):
        """Test getting the history of a non-existent chat"""
        # Create a mock for the session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Set the result to None
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_result.scalars.return_value.first.return_value = None
        
        # Call the method
        result = await Message.get_chat_history(mock_session, 123456)
        
        # Check that an empty list is returned
        assert result == []
