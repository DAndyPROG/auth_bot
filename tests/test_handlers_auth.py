import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from handlers.auth import cmd_start, cmd_logout, check_auth_status, router, AuthStates
from handlers.states import UserForm
from utils.database import User, Chat, Message as MessageModel

# Tests for cmd_start
@pytest.mark.asyncio
async def test_cmd_start_new_user(mock_message, mock_state, async_session):
    """Test processing the /start command for a new user"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/start"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.User.create_or_update') as mock_create_user, \
         patch('handlers.auth.Chat.create') as mock_create_chat, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.session_manager.start_session') as mock_start_session, \
         patch('handlers.auth.auth0_client.start_device_flow') as mock_start_device_flow, \
         patch('asyncio.create_task') as mock_create_task:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        mock_get_user.return_value = None  # User does not exist
        
        # Mock for User.create_or_update
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = None
        mock_user.is_active = False
        mock_create_user.return_value = mock_user
        
        # Mock for Chat.create
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_create_chat.return_value = mock_chat
        
        # Mock for auth0_client.start_device_flow
        mock_start_device_flow.return_value = (
            "https://example.com/verify",
            "TEST-CODE",
            1800
        )
        
        # Call the function
        await cmd_start(mock_message, mock_state)
        
        # Check that the dependencies were called correctly
        mock_get_user.assert_awaited_once_with(async_session, 123456)
        mock_create_user.assert_awaited_once_with(async_session, 123456)
        mock_create_chat.assert_awaited_once_with(async_session, 1, 654321)
        mock_log_message.assert_awaited_once_with(
            async_session, 
            chat_id=654321, 
            text="/start", 
            from_user=True,
            message_id=1
        )
        mock_start_session.assert_awaited_once_with(123456, async_session)
        mock_start_device_flow.assert_awaited_once_with(123456)
        
        # Check the state
        mock_state.set_state.assert_awaited_once_with(AuthStates.waiting_for_auth)
        
        # Check the response to the user
        mock_message.answer.assert_awaited_once()
        
        # Check thatetheaauthorization check waswstarteded
        mock_create_task.assert_called_once()
        assert "check_auth_status" in str(mock_create_task.call_args)

@pytest.mark.asyncio
async def test_cmd_start_existing_authorized_user(mock_message, mock_state, async_session):
    """Test processing the /start command for an existing authorized user"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/start"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.session_manager.is_authorized') as mock_is_authorized, \
         patch('handlers.auth.session_manager.set_authorized') as mock_set_authorized:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for User.get_by_telegram_id
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = "auth0|test123"
        mock_user.auth0_data = {"sub": "auth0|test123", "name": "Test User"}
        mock_user.is_active = True
        mock_get_user.return_value = mock_user
        
        # Mock for session_manager.is_authorized
        mock_is_authorized.return_value = False  # The user is authorized, but the session is not active    
        
        # Call the function
        await cmd_start(mock_message, mock_state)
        
        # Check that the dependencies were called correctly
        mock_get_user.assert_awaited_once_with(async_session, 123456)
        mock_log_message.assert_called() # Called at least once
        
        # Check that the authorization was set in session_manager
        mock_set_authorized.assert_awaited_once_with(
            123456, async_session, "auth0|test123", {"sub": "auth0|test123", "name": "Test User"}
        )
        
        # Check the state
        mock_state.set_state.assert_awaited_once_with(AuthStates.authorized)
        
        # Check the response to the user
        assert mock_message.answer.await_count >= 2  # For JSON data and a message

@pytest.mark.asyncio
async def test_cmd_start_with_auth_error(mock_message, mock_state, async_session):
    """Test processing the /start command with an authorization error"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/start"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.User.create_or_update') as mock_create_user, \
         patch('handlers.auth.Chat.create') as mock_create_chat, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.session_manager.start_session') as mock_start_session, \
         patch('handlers.auth.auth0_client.start_device_flow', side_effect=Exception("Auth error")) as mock_start_device_flow:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        mock_get_user.return_value = None  # The user does not exist
        
        # Mock for User.create_or_update
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = None
        mock_user.is_active = False
        mock_create_user.return_value = mock_user
        
        # Mock for Chat.create
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_create_chat.return_value = mock_chat
        
        # Call the function
        await cmd_start(mock_message, mock_state)
        
        # Check that the error response was sent
        mock_message.answer.assert_called_with(
            '❌ Error during authorization: Auth error.\nMake sure your Auth0 settings are correct.'
        )
        
        # Check that the response was logged
        assert mock_log_message.await_count >= 2  # For the input message and the response

@pytest.mark.asyncio
async def test_cmd_start_deactivated_user(mock_message, mock_state, async_session):
    """Test processing the /start command for a deactivated user"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/start"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.session_manager.start_session') as mock_start_session, \
         patch('handlers.auth.auth0_client.start_device_flow') as mock_start_device_flow, \
         patch('asyncio.create_task') as mock_create_task:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for User.get_by_telegram_id
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.auth0_id = "auth0|test123"
        mock_user.auth0_data = {"sub": "auth0|test123", "name": "Test User"}
        mock_user.is_active = False
        mock_get_user.return_value = mock_user
        
        # Mock for auth0_client.start_device_flow
        mock_start_device_flow.return_value = (
            "https://example.com/verify",
            "TEST-CODE",
            1800
        )
        
        # Call the function
        await cmd_start(mock_message, mock_state)
        
        # Check that the dependencies were called correctly
        mock_get_user.assert_awaited_once_with(async_session, 123456)
        mock_start_session.assert_awaited_once_with(123456, async_session)
        mock_start_device_flow.assert_awaited_once_with(123456)
        
        # Check the state
        mock_state.set_state.assert_awaited_once_with(AuthStates.waiting_for_auth)
        
        # Check that the response contains information about a new authorization
        assert any("You need to go through a new authorization" in str(call) for call in mock_message.answer.call_args_list)
        
        # Check that the authorization check was started
        mock_create_task.assert_called_once()

@pytest.mark.asyncio
async def test_cmd_start_with_general_error(mock_message, mock_state):
    """Test processing the /start command with a general error"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/start"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await cmd_start(mock_message, mock_state)
        
        # Check that the error response was sent
        mock_message.answer.assert_awaited_once_with(
            "❌ An error occurred: Database error. Please try again later."
        )

# Tests for check_auth_status
@pytest.mark.asyncio
async def test_check_auth_status_success(mock_message, mock_state, async_session):
    """Test successful authorization status check"""
    # Parameters of the function
    user_id = 123456
    chat_id = 654321
    
    # Create a mock for message.answer (for status_message)
    mock_status_message = AsyncMock()
    mock_message.answer.return_value = mock_status_message
    
    # Patch the dependencies
    with patch('handlers.auth.auth0_client.poll_device_flow') as mock_poll, \
         patch('handlers.auth.auth0_client.get_user_info') as mock_get_user_info, \
         patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.User.create_or_update') as mock_create_user, \
         patch('handlers.auth.session_manager.set_authorized') as mock_set_authorized, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('asyncio.sleep') as mock_sleep:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # The first call to poll_device_flow returns a token
        mock_poll.return_value = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }
        
        # get_user_info returns user data
        mock_get_user_info.return_value = {
            "sub": "auth0|test123",
            "name": "Test User",
            "email": "test@example.com"
        }
        
        # create_or_update returns a user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_create_user.return_value = mock_user
        
        # Call the function
        await check_auth_status(mock_message, mock_state, user_id, chat_id)
        
        # Check that poll_device_flow was called
        mock_poll.assert_awaited_once_with(user_id)
        
        # Check that get_user_info was called with the correct token
        mock_get_user_info.assert_awaited_once()
        
        # Check that create_or_update was called with the correct parameters
        mock_create_user.assert_awaited_once()
        assert user_id in mock_create_user.call_args[0]
        assert "auth0|test123" in mock_create_user.call_args[0]
        assert True in mock_create_user.call_args[1].values()  # is_active=True
        
        # Check that set_authorized was called
        mock_set_authorized.assert_awaited_once()
        
        # Check that status_message was updated
        mock_status_message.edit_text.assert_called_with("✅ Authorization successful! Fill in additional data.")
        
        # Check that the state was changed to waiting_full_name
        mock_state.set_state.assert_called_with(UserForm.waiting_full_name)
        
        # Check the number of messages
        assert mock_message.answer.await_count >= 3  # JSON data, success message and request for a name

@pytest.mark.asyncio
async def test_check_auth_status_timeout(mock_message, mock_state, async_session):
    """Test timeout when checking authorization status"""
    # Parameters of the function
    user_id = 123456
    chat_id = 654321
    
    # Create a mock for message.answer (for status_message)
    mock_status_message = AsyncMock()
    mock_message.answer.return_value = mock_status_message
    
    # Patch the dependencies
    with patch('handlers.auth.auth0_client.poll_device_flow') as mock_poll, \
         patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.session_manager.close_session') as mock_close_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('asyncio.sleep') as mock_sleep:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # poll_device_flow always returns None (authorization did not happen)
        mock_poll.return_value = None
        
        # Call the function
        await check_auth_status(mock_message, mock_state, user_id, chat_id)
        
        # Check that poll_device_flow was called max_attempts times
        assert mock_poll.await_count == 30
        
        # Check that close_session was called
        mock_close_session.assert_awaited_once_with(user_id)
        
        # Check that the state was cleared
        mock_state.clear.assert_awaited_once()
        
        # Check that status_message was updated
        mock_status_message.edit_text.assert_called_with("⏱️ Time out waiting for authorization")
        
        # Check that the timeout message was sent
        assert any("Time out waiting for authorization" in str(call) for call in mock_message.answer.call_args_list)

@pytest.mark.asyncio
async def test_check_auth_status_error(mock_message, mock_state, async_session):
    """Test processing an error when checking authorization status"""
    # Parameters of the function
    user_id = 123456
    chat_id = 654321
    
    # Create a mock for message.answer (for status_message)
    mock_status_message = AsyncMock()
    mock_message.answer.return_value = mock_status_message
    
    # Patch the dependencies
    with patch('handlers.auth.auth0_client.poll_device_flow', side_effect=Exception("Auth error")) as mock_poll, \
         patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.session_manager.close_session') as mock_close_session, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Call the function
        await check_auth_status(mock_message, mock_state, user_id, chat_id)
        
        # Check that poll_device_flow was called
        mock_poll.assert_awaited_once()
        
        # Check that close_session was called
        mock_close_session.assert_awaited_once_with(user_id)
        
        # Check that the state was cleared
        mock_state.clear.assert_awaited_once()
        
        # Check that the error message was sent
        assert any("Error during authorization: Auth error" in str(call) for call in mock_message.answer.call_args_list)

# Tests for cmd_logout
@pytest.mark.asyncio
async def test_cmd_logout_success(mock_message, mock_state, async_session):
    """Test successful logout"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/logout"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.select') as mock_select, \
         patch('handlers.auth.MessageModel.log_message') as mock_log_message, \
         patch('handlers.auth.User.deactivate') as mock_deactivate, \
         patch('handlers.auth.session_manager.close_session') as mock_close_session:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for execute and the query result
        mock_chat = MagicMock()
        mock_chat.id = 1
        mock_execute_result = AsyncMock()
        mock_execute_result.scalars.return_value.first.return_value = mock_chat
        async_session.execute.return_value = mock_execute_result
        
        # Call the function
        await cmd_logout(mock_message, mock_state)
        
        # Check that the dependencies were called correctly
        async_session.execute.assert_awaited_once()
        mock_log_message.assert_awaited()  # Called at least once
        mock_deactivate.assert_awaited_once_with(async_session, 123456)
        mock_close_session.assert_awaited_once_with(123456)
        
        # Check that the state was cleared
        mock_state.clear.assert_awaited_once()
        
        # Check that the response to the user was sent
        assert any("You have successfully logged out of the system" in str(call) for call in mock_message.answer.call_args_list)

@pytest.mark.asyncio
async def test_cmd_logout_no_chat(mock_message, mock_state, async_session):
    """Test logout when the chat is not found"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/logout"
    
    # Patch the dependencies
    with patch('handlers.auth.db.async_session') as mock_db_session, \
         patch('handlers.auth.select') as mock_select, \
         patch('handlers.auth.User.get_by_telegram_id') as mock_get_user, \
         patch('handlers.auth.Chat.create') as mock_create_chat:
        
        # Set the mock results
        mock_db_session.return_value.__aenter__.return_value = async_session
        
        # Mock for execute and the query result - the chat is not found
        mock_execute_result = AsyncMock()
        mock_execute_result.scalars.return_value.first.return_value = None
        async_session.execute.return_value = mock_execute_result
        
        # Mock for User.get_by_telegram_id - the user is not found
        mock_get_user.return_value = None
        
        # Call the function
        await cmd_logout(mock_message, mock_state)
        
        # Check that the response to the user was sent
        mock_message.answer.assert_awaited_once_with("Please start working with the command /start")

@pytest.mark.asyncio
async def test_cmd_logout_error(mock_message, mock_state):
    """Test processing an error when logging out"""
    # Set the mock objects
    mock_message.from_user.id = 123456
    mock_message.chat.id = 654321
    mock_message.text = "/logout"
    
    # Patch for calling a general error
    with patch('handlers.auth.db.async_session', side_effect=Exception("Database error")):
        # Call the function
        await cmd_logout(mock_message, mock_state)
        
        # Check that the error message was sent
        mock_message.answer.assert_awaited_once_with(
            "Error during logout: Database error. Please try again."
        )
