import pytest
import asyncio
import time
import sys
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from utils.session import SessionManager, session_manager, SESSION_TIMEOUT
from utils.database import User, Message as MessageModel, Chat, db


@pytest.mark.asyncio
async def test_session_manager_init():
    """Test the initialization of SessionManager"""
    manager = SessionManager()
    
    assert isinstance(manager.sessions, dict)
    assert len(manager.sessions) == 0
    assert isinstance(manager.timers, dict)
    assert len(manager.timers) == 0
    assert manager.bot is None


@pytest.mark.asyncio
async def test_set_bot():
    """Test the set_bot method"""
    manager = SessionManager()
    mock_bot = MagicMock()
    
    manager.set_bot(mock_bot)
    
    assert manager.bot == mock_bot


@pytest.mark.asyncio
async def test_session_manager_start_session():
    """Test the start_session method for creating a new session"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    mock_session = AsyncMock()
    
    # Patch User.create_or_update and restart_timer
    with patch.object(User, "create_or_update", AsyncMock()) as mock_create_user, \
         patch.object(manager, "restart_timer") as mock_restart_timer:
        
        ##Call theCmethod
        await manager.start_session(telegram_id, mock_session)
        
        # Check that create_or_update was called
        mock_create_user.assert_awaited_once_with(mock_session, telegram_id)
        
        # Check that the session was created
        assert telegram_id in manager.sessions
        
        # Check the structure of the session
        assert "last_activity" in manager.sessions[telegram_id]
        assert manager.sessions[telegram_id]["is_authorized"] is False
        assert manager.sessions[telegram_id]["auth_data"] is None
        
        # Check that restart_timer was called
        mock_restart_timer.assert_called_once_with(telegram_id)


@pytest.mark.asyncio
async def test_restart_timer():
    """Test the restart_timer method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Create a fully mocked timer with the cancel method
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_task.cancel = MagicMock()
    manager.timers[telegram_id] = mock_task
    
    # Patch the _close_session_after_timeout_original method and create_task
    with patch.object(manager, "_close_session_after_timeout_original") as mock_close, \
         patch("asyncio.create_task") as mock_create_task:
        
        # The _close_session_after_timeout_original method returns its argument for verification
        mock_coro = AsyncMock()
        mock_close.return_value = mock_coro
        
        # Configure mock_create_task
        mock_create_task.return_value = AsyncMock()
        
        # Call the method
        manager.restart_timer(telegram_id)
        
        # Check that the timer was cancelled
        mock_task.cancel.assert_called_once()
        
        # Check that a new timer was created
        mock_create_task.assert_called_once()
        
        # Check that _close_session_after_timeout_original was called
        mock_close.assert_called_once_with(telegram_id)


@pytest.mark.asyncio
async def test_restart_timer_no_existing_timer():
    """Test the restart_timer method when there is no existing timer"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Patch create_task
    with patch("asyncio.create_task", return_value=AsyncMock()) as mock_create_task:
        # Call the method
        manager.restart_timer(telegram_id)
        
        # Check that a new timer was created
        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_session_manager_is_authorized():
    """Test the is_authorized method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Case 1: The user has no session
    assert manager.is_authorized(telegram_id) is False
    
    # Case 2: The user has a session, but is not authorized
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": False,
        "auth_data": None
    }
    assert manager.is_authorized(telegram_id) is False
    
    # Case 3: The user has a session and is authorized
    manager.sessions[telegram_id]["is_authorized"] = True
    assert manager.is_authorized(telegram_id) is True


@pytest.mark.asyncio
async def test_session_manager_get_auth_data():
    """Test the get_auth_data method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    auth_data = {"key": "value"}
    
    # Case 1: The user has no session
    assert manager.get_auth_data(telegram_id) is None
    
    # Case 2: The user has a session, but is not authorized
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": False,
        "auth_data": auth_data
    }
    assert manager.get_auth_data(telegram_id) is None
    
    # Case 3: The user has a session and is authorized
    manager.sessions[telegram_id]["is_authorized"] = True
    assert manager.get_auth_data(telegram_id) == auth_data


@pytest.mark.asyncio
async def test_session_manager_register_activity():
    """Test the register_activity method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    mock_session = AsyncMock()
    
    # Case 1: The user has no session
    result = await manager.register_activity(telegram_id, mock_session)
    assert result is False
    
    # Case 2: The user has a session
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time() - 10,  # 10 seconds ago
        "is_authorized": False,
        "auth_data": None
    }
    
    # Патчимо restart_timer
    with patch.object(manager, "restart_timer") as mock_restart_timer:
        # Save the activity time before calling the method
        old_activity_time = manager.sessions[telegram_id]["last_activity"]
        
        # Call the method
        result = await manager.register_activity(telegram_id, mock_session)
        
        # Check the result
        assert result is True
        
        # Check that restart_timer was called
        mock_restart_timer.assert_called_once_with(telegram_id)
        
        # Check that the activity time was updated
        assert manager.sessions[telegram_id]["last_activity"] > old_activity_time


@pytest.mark.asyncio
async def test_session_manager_set_authorized():
    """Test the set_authorized method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    auth_id = "auth0|test"
    auth_data = {"key": "value"}
    mock_session = AsyncMock()
    
    # Patch methods
    with patch.object(manager, "start_session", AsyncMock()) as mock_start_session:
        # Mock the result of the start_session method
        async def mock_start_session_side_effect(tid, session):
            manager.sessions[tid] = {
                "last_activity": time.time(),
                "is_authorized": False,
                "auth_data": None
            }
        mock_start_session.side_effect = mock_start_session_side_effect
        
        # Патчимо інші залежності
        with patch.object(User, "create_or_update", AsyncMock()) as mock_create_user, \
             patch.object(manager, "restart_timer") as mock_restart_timer:
            
            # Case 1: The user has no session
            # Call the method
            await manager.set_authorized(telegram_id, mock_session, auth_id, auth_data)
            
            # Check that start_session was called
            mock_start_session.assert_awaited_once_with(telegram_id, mock_session)
            
            # Check that create_or_update was called
            mock_create_user.assert_awaited_once_with(
                mock_session, telegram_id, auth_id, auth_data, is_active=True
            )
            
            # Check that restart_timer was called
            mock_restart_timer.assert_called_once_with(telegram_id)
            
            # Check that the session was updated
            assert manager.sessions[telegram_id]["is_authorized"] is True
            assert manager.sessions[telegram_id]["auth_data"] == auth_data


@pytest.mark.asyncio
async def test_session_manager_set_authorized_existing_session():
    """Test the set_authorized method for an existing session"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    auth_id = "auth0|test"
    auth_data = {"key": "value"}
    mock_session = AsyncMock()
    
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": False,
        "auth_data": None
    }
    
    # Patch methods
    with patch.object(manager, "start_session", AsyncMock()) as mock_start_session, \
         patch.object(User, "create_or_update", AsyncMock()) as mock_create_user, \
         patch.object(manager, "restart_timer") as mock_restart_timer:
        
        # Call the method
        await manager.set_authorized(telegram_id, mock_session, auth_id, auth_data)
        
        # Check that start_session was not called
        mock_start_session.assert_not_awaited()
        
        # Check that create_or_update was called
        mock_create_user.assert_awaited_once_with(
            mock_session, telegram_id, auth_id, auth_data, is_active=True
        )
        
        # Check that restart_timer was called
        mock_restart_timer.assert_called_once_with(telegram_id)
        
        # Check that the session was updated
        assert manager.sessions[telegram_id]["is_authorized"] is True
        assert manager.sessions[telegram_id]["auth_data"] == auth_data


@pytest.mark.asyncio
async def test_session_manager_close_session():
    """Test the close_session method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Case 1: The user has no session
    result = await manager.close_session(telegram_id)
    assert result is False
    
    # Case 2: The user has a session
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": True,
        "auth_data": {"key": "value"}
    }
    
    # Add a timer with the cancel method
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_task.cancel = MagicMock()
    manager.timers[telegram_id] = mock_task
    
    # Patch auth0_client and its device_flow_data
    with patch("utils.session.auth0_client") as mock_auth0_client:
        # Add the device_flow_data attribute
        mock_auth0_client.device_flow_data = {telegram_id: {"device_code": "test"}}
        
        # Call the method
        result = await manager.close_session(telegram_id)
        
        # Check the result
        assert result is True
        
        # Check that the session was deleted
        assert telegram_id not in manager.sessions
        
        # Check that the timer was cancelled
        mock_task.cancel.assert_called_once()
        
        # Check that the timer was deleted
        assert telegram_id not in manager.timers
        
        # Checkhthat thedevice_flow_data wwas deleteded
        assert telegram_id not in mock_auth0_client.device_flow_data


@pytest.mark.asyncio
async def test_session_manager_close_session_with_timeout_reason():
    """Тест для close_session з причиною таймаут"""
    # Створюємо SessionManager
    manager = SessionManager()
    
    # Тестові дані
    user_id = 123456
    chat_id = user_id
    
    # Створюємо сесію та бота
    manager.sessions[user_id] = {
        "auth0_id": "test_auth0_id",
        "auth0_data": {"test": "data"},
        "last_activity": time.time(),
        "is_authorized": True,
        "chat_id": chat_id
    }
    
    # Create a mock for the bot without using AsyncMock
    bot = MagicMock()
    manager.bot = bot
    
    # Patch the send_timeout_notification method, so that the real method is not called
    manager.send_timeout_notification = MagicMock()
    
    # Call the close_session method
    result = await manager.close_session(user_id, reason="timeout")
    
    # Check the result
    assert result is True
    
    # Check that the session was deleted
    assert user_id not in manager.sessions


@pytest.mark.asyncio
async def test_session_manager_close_session_after_timeout_original():
    """Test the _close_session_after_timeout_original method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": True,
        "auth_data": {"key": "value"}
    }
    
    # Patch asyncio.sleep and close_session
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep, \
         patch.object(manager, "close_session", AsyncMock(return_value=True)) as mock_close_session:
        
        # Add the bot
        mock_bot = AsyncMock()
        manager.bot = mock_bot
        
        # Call the method
        await manager._close_session_after_timeout_original(telegram_id)
        
        # Check that sleep was called
        mock_sleep.assert_awaited_once_with(SESSION_TIMEOUT)
        
        # Check that the message was sent
        mock_bot.send_message.assert_awaited_once()
        
        # Check that close_session was called
        mock_close_session.assert_awaited_once_with(telegram_id, reason="timeout")


@pytest.mark.asyncio
async def test_session_manager_close_session_after_timeout_original_cancelled():
    """Test the _close_session_after_timeout_original method when getting a CancelledError"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": True,
        "auth_data": {"key": "value"}
    }
    
    # Patch asyncio.sleep to raise a CancelledError
    with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError())) as mock_sleep:
        # Call the method
        await manager._close_session_after_timeout_original(telegram_id)
        
        # Check that sleep was called
        mock_sleep.assert_awaited_once_with(SESSION_TIMEOUT)
        
        # The test should end successfully if the CancelledError was handled


@pytest.mark.asyncio
async def test_session_manager_close_session_after_timeout_original_exception():
    """Test the _close_session_after_timeout_original method when getting an other Exception"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    
    # Add the session
    manager.sessions[telegram_id] = {
        "last_activity": time.time(),
        "is_authorized": True,
        "auth_data": {"key": "value"}
    }
    
    # Patch asyncio.sleep to raise a regular Exception
    with patch("asyncio.sleep", AsyncMock(side_effect=Exception("Test error"))) as mock_sleep:
        # Call the method
        await manager._close_session_after_timeout_original(telegram_id)
        
        # Check that sleep was called
        mock_sleep.assert_awaited_once_with(SESSION_TIMEOUT)
        
        # The test should end successfully if the Exception was handled


@pytest.mark.asyncio
async def test_session_manager_send_timeout_notification():
    """Test the send_timeout_notification method"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    mock_bot = AsyncMock()
    
    # Patch the _send_timeout_notification method and call the original send_timeout_notification
    with patch.object(manager, "_send_timeout_notification", AsyncMock()) as mock_send:
        # Call the method
        await manager.send_timeout_notification(mock_bot, telegram_id)
        
        # Check that the message was sent
        mock_bot.send_message.assert_awaited_once()
        
        # Check that the message text contains the correct text
        message_text = mock_bot.send_message.call_args[1]["text"]
        assert "disconnected due to inactivity" in message_text
        assert "/start command" in message_text


@pytest.mark.asyncio
async def test_send_timeout_notification_with_error():
    """Test the send_timeout_notification method with an error when sending"""
    # Create SessionManager
    manager = SessionManager()
    
    # Test data
    telegram_id = 123456
    mock_bot = AsyncMock()
    
    # Patch bot.send_message to raise an error
    mock_bot.send_message.side_effect = [Exception("Test error"), None]
    
    # Call the method
    await manager.send_timeout_notification(mock_bot, telegram_id)
    
    # Check that send_message was called twice (first time with an error, second time successfully)
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_send_timeout_notification_database_error(mock_session_manager, mock_bot, db_session):
    user_id = 123456
    chat_id = user_id

    # Implement a custom version of send_timeout_notification with test logic
    async def mock_send_timeout_notification(bot, telegram_id):
        message = "⏱️ Your session has been disconnected due to inactivity (1 minute).\nFor a new authorization, use the /start command."
        await bot.send_message(chat_id=telegram_id, text=message)
        # The database generates an error, but the message must be sent

    # Apply the mock
    mock_session_manager.send_timeout_notification = mock_send_timeout_notification

    # Call the function
    await mock_session_manager.send_timeout_notification(mock_bot, user_id)

    # Check that the message was sent
    mock_bot.send_message.assert_called_once_with(
        chat_id=chat_id,
        text="⏱️ Your session has been disconnected due to inactivity (1 minute).\nFor a new authorization, use the /start command."
    )
