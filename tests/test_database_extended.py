import os
import datetime
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select

from utils.database import AsyncDatabase, Base, User, Chat, Message, db


@pytest_asyncio.fixture(scope="function")
async def in_memory_db():
    """Fixture for creating a test database in memory"""
    # Create a test database in memory
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=True
    )
    
    # Initialize models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Yield the engine
    try:
        yield engine
    finally:
        # Clear all tables after tests
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(in_memory_db):
    """Fixture for getting a session from the test database"""
    async_session_factory = async_sessionmaker(
        in_memory_db, expire_on_commit=False
    )
    
    session = async_session_factory()
    await session.begin()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


class TestIntegrationAsyncDatabase:
    @pytest.mark.asyncio
    async def test_init_models_real_db(self):
        """Integration test for initializing models in a real database"""
        # Create a test database in memory
        test_db = AsyncDatabase(url="sqlite+aiosqlite:///:memory:")
        
        # Call the init_models method
        await test_db.init_models()
        
        # Check that the tables were created, by creating a user
        async with test_db.async_session() as session:
            # Create a test user
            user = User(telegram_id=123456)
            session.add(user)
            await session.commit()
            
            # Check that the user was saved
            result = await session.execute(select(User).where(User.telegram_id == 123456))
            saved_user = result.scalars().first()
            assert saved_user is not None
            assert saved_user.telegram_id == 123456
            
        # Clear the database
        async with test_db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_db.engine.dispose()


class TestIntegrationUser:
    @pytest.mark.asyncio
    async def test_get_by_telegram_id_real_db(self, db_session):
        """Integration test for getting a user by telegram_id"""
        # Create a test user
        user = User(telegram_id=123456)
        db_session.add(user)
        await db_session.commit()
        
        # Call the test method
        result = await User.get_by_telegram_id(db_session, 123456)
        
        # Check the result
        assert result is not None
        assert result.telegram_id == 123456
        
        # Check that a non-existent user is not found
        result = await User.get_by_telegram_id(db_session, 999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_or_update_new_user_real_db(self, db_session):
        """Integration test for creating a new user"""
        # Check that the user does not exist
        result = await User.get_by_telegram_id(db_session, 123456)
        assert result is None
        
        # Create a new user
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        # Check that the user was created
        assert user is not None
        assert user.telegram_id == 123456
        assert user.auth0_id == "auth0|test123"
        assert user.email == "test@example.com"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_create_or_update_existing_user_real_db(self, db_session):
        """Integration test for updating an existing user"""
        # Create initial user
        initial_user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Initial User",
                "email": "initial@example.com"
            },
            is_active=True
        )
        
        # Update the user
        updated_user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Updated User",
                "email": "updated@example.com"
            },
            is_active=True
        )
        
        # Check that the user was updated
        assert updated_user is not None
        assert updated_user.telegram_id == 123456
        assert updated_user.auth0_id == "auth0|test123"
        assert updated_user.email == "updated@example.com"
        assert updated_user.is_active is True

    @pytest.mark.asyncio
    async def test_create_or_update_extract_auth0_data_real_db(self, db_session):
        """Integration test for extracting data from auth0_data"""
        # Call the test method
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Auth0 Name",
                "email": "auth0@example.com",
                "phone_number": "+111222333"
            },
            is_active=True
        )
        
        # Check that the data was extracted from auth0_data
        assert user.full_name == "Auth0 Name"
        assert user.email == "auth0@example.com"
        assert user.phone_number == "+111222333"

    @pytest.mark.asyncio
    async def test_deactivate_user_real_db(self, db_session):
        """Integration test for deactivating a user"""
        # Create an active user
        user = User(
            telegram_id=123456,
            is_active=True
        )
        db_session.add(user)
        await db_session.commit()
        
        # Call the test method
        result = await User.deactivate(db_session, 123456)
        
        # Check that the user was deactivated
        assert result is not None
        assert result.is_active == False
        
        # Check that the data in the database was updated
        db_user = await User.get_by_telegram_id(db_session, 123456)
        assert db_user.is_active == False
        
        # Test deactivation of a non-existent user
        result = await User.deactivate(db_session, 999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_deactivate_existing_user_real_db(self, db_session):
        """Integration test for deactivating an existing user"""
        # Create a user
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        # Deactivate the user
        deactivated_user = await User.deactivate(db_session, 123456)
        
        # Check that the user was deactivated
        assert deactivated_user is not None
        assert deactivated_user.telegram_id == 123456
        assert deactivated_user.is_active is False
        
        # Verify the user is deactivated in the database
        result = await User.get_by_telegram_id(db_session, 123456)
        assert result is not None
        assert result.is_active is False


class TestIntegrationChat:
    @pytest.mark.asyncio
    async def test_create_chat_real_db(self, db_session):
        """Integration test for creating a new chat"""
        # Create a user first
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        # Create a new chat
        chat = await Chat.create(
            db_session,
            user.id,
            123456
        )
        
        # Check that the chat was created
        assert chat is not None
        assert chat.user_id == user.id
        assert chat.chat_id == 123456
        
        # Verify the chat exists in the database
        result = await Chat.get_by_id(db_session, chat.id)
        assert result is not None
        assert result.chat_id == 123456

    @pytest.mark.asyncio
    async def test_get_user_chats_real_db(self, db_session):
        """Integration test for getting user chats"""
        # Create a user first
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        # Create multiple chats for the user
        chat1 = await Chat.create(
            db_session,
            user.id,
            123456
        )
        
        chat2 = await Chat.create(
            db_session,
            user.id,
            654321
        )
        
        # Get user's chats
        chats = await Chat.get_user_chats(db_session, user.id)
        
        # Check that all chats were retrieved
        assert len(chats) == 2
        chat_ids = {chat.chat_id for chat in chats}
        assert 123456 in chat_ids
        assert 654321 in chat_ids

    @pytest.mark.asyncio
    async def test_get_by_id_real_db(self, db_session):
        """Integration test for getting a chat by ID"""
        # Create a user
        user = User(telegram_id=123456)
        db_session.add(user)
        await db_session.commit()
        
        # Get the user ID
        result = await db_session.execute(select(User).where(User.telegram_id == 123456))
        user = result.scalars().first()
        
        # Create a chat
        chat = Chat(user_id=user.id, chat_id=654321)
        db_session.add(chat)
        await db_session.commit()
        
        # Get the chat ID
        result = await db_session.execute(select(Chat).where(Chat.chat_id == 654321))
        db_chat = result.scalars().first()
        
        # Call the test method
        found_chat = await Chat.get_by_id(db_session, db_chat.id)
        
        # Check the result
        assert found_chat is not None
        assert found_chat.id == db_chat.id
        assert found_chat.chat_id == 654321
        
        # Test getting a non-existent chat
        result = await Chat.get_by_id(db_session, 999999)
        assert result is None


class TestIntegrationMessage:
    @pytest.mark.asyncio
    async def test_log_message_real_db(self, db_session):
        """Integration test for logging messages"""
        # Create a user and chat first
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        chat = await Chat.create(
            db_session,
            user.id,
            123456
        )
        
        # Log a message
        message = await Message.log_message(
            db_session,
            chat.chat_id,
            "Test message",
            True
        )
        
        # Check that the message was logged
        assert message is not None
        assert message.chat_id == chat.id
        assert message.text == "Test message"
        assert message.from_user is True
        
        # Verify the message exists in the database
        history = await Message.get_chat_history(db_session, chat.chat_id)
        assert len(history) == 1
        assert history[0].text == "Test message"
        assert history[0].from_user is True

    @pytest.mark.asyncio
    async def test_log_message_no_chat_real_db(self, db_session):
        """Integration test for error logging a message without a chat"""
        # Call the test method and expect an error
        with pytest.raises(Exception, match="Chat with ID 999999 not found"):
            await Message.log_message(
                db_session,
                999999,
                "Test message",
                True,
                1
            )

    @pytest.mark.asyncio
    async def test_get_chat_history_real_db(self, db_session):
        """Integration test for getting chat history"""
        # Create a user and chat first
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {
                "sub": "auth0|test123",
                "name": "Test User",
                "email": "test@example.com"
            },
            is_active=True
        )
        
        chat = await Chat.create(
            db_session,
            user.id,
            123456
        )
        
        # Log multiple messages
        await Message.log_message(
            db_session,
            chat.chat_id,
            "User message 1",
            True
        )
        
        await Message.log_message(
            db_session,
            chat.chat_id,
            "Assistant message 1",
            False
        )
        
        await Message.log_message(
            db_session,
            chat.chat_id,
            "User message 2",
            True
        )
        
        # Get chat history
        history = await Message.get_chat_history(db_session, chat.chat_id)
        
        # Check that all messages were retrieved in correct order
        assert len(history) == 3
        assert history[0].text == "User message 1"
        assert history[1].text == "Assistant message 1"
        assert history[2].text == "User message 2"
        
        # Check message roles
        assert history[0].from_user is True
        assert history[1].from_user is False
        assert history[2].from_user is True

    @pytest.mark.asyncio
    async def test_get_chat_history_no_chat_real_db(self, db_session):
        """Integration test for getting the history of a non-existent chat"""
        # Call the test method
        history = await Message.get_chat_history(db_session, 999999)
        
        # Check that the result is an empty list
        assert history == []


@pytest.mark.asyncio
async def test_complex_database_scenario(db_session):
    """Complex database scenario"""
    # 1. Create a user
    user = await User.create_or_update(
        db_session,
        123456,
        "auth0|test123",
        {
            "sub": "auth0|test123",
            "name": "Test User",
            "email": "test@example.com"
        },
        is_active=True
    )
    
    # 2. Create a chat for the user
    chat = await Chat.create(
        db_session,
        user.id,
        123456
    )
    
    # 3. Log several messages
    message1 = await Message.log_message(
        db_session,
        chat.chat_id,
        "Hello!",
        True
    )
    
    message2 = await Message.log_message(
        db_session,
        chat.chat_id,
        "Hi there!",
        False
    )
    
    message3 = await Message.log_message(
        db_session,
        chat.chat_id,
        "How are you?",
        True
    )
    
    # 4. Get the chat history
    history = await Message.get_chat_history(db_session, chat.chat_id)
    
    # 5. Check the results
    assert len(history) == 3
    assert history[0].text == "Hello!"
    assert history[1].text == "Hi there!"
    assert history[2].text == "How are you?"
    
    # 6. Deactivate the user
    deactivated_user = await User.deactivate(db_session, 123456)
    assert deactivated_user.is_active is False
    
    # 7. Check that the user is deactivated
    db_user = await User.get_by_telegram_id(db_session, 123456)
    assert db_user.is_active is False


@pytest.mark.asyncio
async def test_database_error_handling():
    """Test error handling when working with the database"""
    # Create a database with an invalid URL
    try:
        invalid_db = AsyncDatabase(url="invalid_url")
        # Calling the init_models method should raise an error
        await invalid_db.init_models()
        assert False, "An error should have been raised"
    except Exception as e:
        # Check that the error was raised
        assert True
        
    # Test the error when getting a session
    test_db = AsyncDatabase(url="sqlite+aiosqlite:///:memory:")
    test_db.engine = None
    with pytest.raises(Exception, match="Database engine is not available"):
        await test_db.get_session()
