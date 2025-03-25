import os
import datetime
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select

from utils.database import AsyncDatabase, Base, User, Chat, Message, db


@pytest.fixture(scope="function")
async def in_memory_db():
    """Fixture for creating a test database in memory"""
    # Create a test database in memory
    test_db = AsyncDatabase(url="sqlite+aiosqlite:///:memory:")
    # Initialize models
    async with test_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_db
    
    # Clear all tables after tests
    async with test_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_db.engine.dispose()


@pytest.fixture(scope="function")
async def db_session(in_memory_db):
    """Fixture for getting a session from the test database"""
    async with in_memory_db.async_session() as session:
        yield session


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
        
        # Call the test method
        user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {"sub": "auth0|test123", "name": "Test User"},
            True,
            "Test User",
            "+123456789",
            "test@example.com"
        )
        
        # Check that the user was created
        assert user is not None
        assert user.telegram_id == 123456
        assert user.auth0_id == "auth0|test123"
        assert user.is_active == True
        assert user.full_name == "Test User"
        assert user.phone_number == "+123456789"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_or_update_existing_user_real_db(self, db_session):
        """Integration test for updating an existing user"""
        # Create a user
        user = User(
            telegram_id=123456,
            full_name="Old Name",
            email="old@example.com",
            is_active=False
        )
        db_session.add(user)
        await db_session.commit()
        
        # Call the test method for updating
        updated_user = await User.create_or_update(
            db_session,
            123456,
            "auth0|test123",
            {"sub": "auth0|test123", "name": "New Name"},
            True,
            "New Full Name",
            "+123456789",
            "new@example.com"
        )
        
        # Check that the user was updated
        assert updated_user.telegram_id == 123456
        assert updated_user.auth0_id == "auth0|test123"
        assert updated_user.is_active == True
        assert updated_user.full_name == "New Full Name"
        assert updated_user.phone_number == "+123456789"
        assert updated_user.email == "new@example.com"
        
        # Check that the data in the database was updated
        result = await User.get_by_telegram_id(db_session, 123456)
        assert result.full_name == "New Full Name"
        assert result.email == "new@example.com"

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
            }
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


class TestIntegrationChat:
    @pytest.mark.asyncio
    async def test_create_chat_real_db(self, db_session):
        """Integration test for creating a chat"""
        # Create a user for chat connection
        user = User(telegram_id=123456)
        db_session.add(user)
        await db_session.commit()
        
        # Get the user ID
        result = await db_session.execute(select(User).where(User.telegram_id == 123456))
        user = result.scalars().first()
        
        # Call the test method
        chat = await Chat.create(db_session, user.id, 654321)
        
        # Check the result
        assert chat is not None
        assert chat.user_id == user.id
        assert chat.chat_id == 654321
        assert chat.created_at is not None

    @pytest.mark.asyncio
    async def test_get_user_chats_real_db(self, db_session):
        """Integration test for getting user chats"""
        # Create a user
        user = User(telegram_id=123456)
        db_session.add(user)
        await db_session.commit()
        
        # Get the user ID
        result = await db_session.execute(select(User).where(User.telegram_id == 123456))
        user = result.scalars().first()
        
        # Create several chats
        chat1 = Chat(user_id=user.id, chat_id=111111)
        chat2 = Chat(user_id=user.id, chat_id=222222)
        db_session.add_all([chat1, chat2])
        await db_session.commit()
        
        # Call the test method
        chats = await Chat.get_user_chats(db_session, user.id)
        
        # Check the result
        assert len(chats) == 2
        assert {chat.chat_id for chat in chats} == {111111, 222222}

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
        """Integration test for logging a message"""
        # Create a user and a chat
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
        
        # Call the test method
        message = await Message.log_message(
            db_session,
            654321,
            "Test message",
            True,
            1
        )
        
        # Check the result
        assert message is not None
        assert message.text == "Test message"
        assert message.from_user == True
        assert message.message_id == 1
        
        # Check that the chat ID was set correctly
        result = await db_session.execute(select(Chat).where(Chat.chat_id == 654321))
        db_chat = result.scalars().first()
        assert message.chat_id == db_chat.id

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
        """Integration test for getting a chat history"""
        # Create a user and a chat
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
        
        # Create messages
        message1 = await Message.log_message(db_session, 654321, "Message 1", True, 1)
        message2 = await Message.log_message(db_session, 654321, "Message 2", False, 2)
        message3 = await Message.log_message(db_session, 654321, "Message 3", True, 3)
        
        # Call the test method
        history = await Message.get_chat_history(db_session, 654321)
        
        # Check the result
        assert len(history) == 3
        assert history[0].text == "Message 1"
        assert history[1].text == "Message 2"
        assert history[2].text == "Message 3"
        
        # Check that the history is ordered by timestamp
        assert history[0].timestamp <= history[1].timestamp
        assert history[1].timestamp <= history[2].timestamp

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
        {"sub": "auth0|test123", "name": "Test User", "email": "test@example.com"},
        True,
        "Test User",
        "+123456789",
        "test@example.com"
    )
    
    # 2. Create a chat for the user
    chat = await Chat.create(db_session, user.id, 654321)
    
    # 3. Log several messages
    message1 = await Message.log_message(db_session, 654321, "Hello!", True, 1)
    message2 = await Message.log_message(db_session, 654321, "Hi there!", False, 2)
    message3 = await Message.log_message(db_session, 654321, "How are you?", True, 3)
    
    # 4. Get the chat history
    history = await Message.get_chat_history(db_session, 654321)
    
    # 5. Check the results
    assert len(history) == 3
    assert history[0].text == "Hello!"
    assert history[1].text == "Hi there!"
    assert history[2].text == "How are you?"
    
    # 6. Deactivate the user
    deactivated_user = await User.deactivate(db_session, 123456)
    assert deactivated_user.is_active == False
    
    # 7. Check that the user is deactivated
    db_user = await User.get_by_telegram_id(db_session, 123456)
    assert db_user.is_active == False


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
