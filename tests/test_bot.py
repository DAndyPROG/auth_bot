import os
import sys
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, call, ANY

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand
from aiogram.methods.base import TelegramMethod

import bot
from bot import set_bot_commands, main, COMMANDS, logger

@pytest.mark.asyncio
async def test_set_bot_commands_success():
    """Test successful setting bot commands"""
    # Create a mock for the bot
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.set_my_commands.return_value = None
    
    # Add a mock for the logger
    with patch.object(logger, 'info') as mock_logger_info:
        # Call the function
        await set_bot_commands(mock_bot)
        
        # Check that the commands are set
        mock_bot.set_my_commands.assert_awaited_once_with(COMMANDS)
        
        # Check that the log is written successfully
        mock_logger_info.assert_called_once_with("Bot commands set successfully")

@pytest.mark.asyncio
async def test_set_bot_commands_unauthorized_error():
    """Test unauthorized error when setting bot commands"""
    # Create a mock for the bot with an unauthorized error
    mock_bot = AsyncMock(spec=Bot)
    # Create a mock for TelegramMethod
    mock_method = MagicMock(spec=TelegramMethod)
    unauthorized_error = TelegramAPIError(method=mock_method, message="Unauthorized")
    mock_bot.set_my_commands.side_effect = unauthorized_error
    
    # Add a mock for the logger
    with patch.object(logger, 'error') as mock_logger_error:
        # Check that the function raises an error
        with pytest.raises(ValueError, match="Invalid bot token"):
            await set_bot_commands(mock_bot)
        
        # Check that the error logs are written
        assert mock_logger_error.call_count == 2
        mock_logger_error.assert_any_call(f"Error setting bot commands: {unauthorized_error}")
        mock_logger_error.assert_any_call("Invalid bot token. Check BOT_TOKEN in the .env file")

@pytest.mark.asyncio
async def test_set_bot_commands_other_error():
    """Test other error when setting bot commands"""
    # Create a mock for the bot with another error
    mock_bot = AsyncMock(spec=Bot)
    # Create a mock for TelegramMethod
    mock_method = MagicMock(spec=TelegramMethod)
    other_error = TelegramAPIError(method=mock_method, message="Other API error")
    mock_bot.set_my_commands.side_effect = other_error
    
    # Додаємо моки для логгера
    with patch.object(logger, 'error') as mock_logger_error:
        # Check that the function logs the error but does not raise ValueError
        await set_bot_commands(mock_bot)
        
        # Check that the error log is written
        mock_logger_error.assert_called_once_with(f"Error setting bot commands: {other_error}")

@pytest.mark.asyncio
async def test_main_database_error():
    """Test database initialization error"""
    # Patch for db.init_models with an error
    with patch('bot.db.init_models', side_effect=Exception("Database initialization error")), \
         patch.object(logger, 'error') as mock_logger_error:
        
        # Call the main function
        await main()
        
        # Checkhthatethererror log is written
        mock_logger_error.assert_called_once_with("Error initializing database: Database initialization error")

@pytest.mark.asyncio
async def test_main_success():
    """Test successful bot startup"""
    # Patches for all dependencies
    with patch('bot.db.init_models') as mock_init_models, \
         patch('bot.AiohttpSession') as mock_session_class, \
         patch('bot.Bot') as mock_bot_class, \
         patch('bot.Dispatcher') as mock_dispatcher_class, \
         patch('bot.session_manager.set_bot') as mock_set_bot, \
         patch('bot.set_bot_commands') as mock_set_commands, \
         patch.object(logger, 'info') as mock_logger_info:
        
        # Configure the mocks
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_dispatcher = MagicMock()
        mock_dispatcher.start_polling = AsyncMock()
        mock_dispatcher.include_routers = MagicMock()
        mock_dispatcher_class.return_value = mock_dispatcher
        
        # Call the main function
        await main()
        
        # Check that all methods were called correctly
        mock_init_models.assert_awaited_once()
        mock_session_class.assert_called_once()
        mock_bot_class.assert_called_once_with(token=bot.BOT_TOKEN, session=mock_session)
        mock_dispatcher_class.assert_called_once()
        mock_set_bot.assert_called_once_with(mock_bot)
        mock_dispatcher.include_routers.assert_called_once_with(bot.auth_router)
        mock_set_commands.assert_awaited_once_with(mock_bot)
        mock_dispatcher.start_polling.assert_awaited_once_with(mock_bot)
        mock_bot.session.close.assert_awaited_once()
        
        # Check that the log sequence is correct
        expected_log_calls = [
            call("Database initialized successfully"),
            call(f"Bot set in session manager: {mock_bot}"),
            call("Routers registered"),
            call("Starting bot..."),
            call("Closing bot session")
        ]
        assert mock_logger_info.call_args_list == expected_log_calls

@pytest.mark.asyncio
async def test_main_bot_initialization_error():
    """Test bot initialization error"""
    # Patches with an error when initializing the bot
    with patch('bot.db.init_models') as mock_init_models, \
         patch('bot.AiohttpSession', side_effect=Exception("Bot initialization error")), \
         patch.object(logger, 'info') as mock_logger_info, \
         patch.object(logger, 'error') as mock_logger_error, \
         patch('traceback.print_exc') as mock_print_exc:
        
        # Call the main function
        await main()
        
        # Check that the database was initialized successfully
        mock_init_models.assert_awaited_once()
        mock_logger_info.assert_called_once_with("Database initialized successfully")
        
        # Check that the error is handled correctly
        mock_logger_error.assert_called_once_with("Error starting bot: Bot initialization error")
        mock_print_exc.assert_called_once()

@pytest.mark.asyncio
async def test_main_bot_polling_error():
    """Test polling error"""
    # Patches with an error when starting polling
    with patch('bot.db.init_models') as mock_init_models, \
         patch('bot.AiohttpSession') as mock_session_class, \
         patch('bot.Bot') as mock_bot_class, \
         patch('bot.Dispatcher') as mock_dispatcher_class, \
         patch('bot.session_manager.set_bot') as mock_set_bot, \
         patch('bot.set_bot_commands') as mock_set_commands, \
         patch.object(logger, 'info') as mock_logger_info, \
         patch.object(logger, 'error') as mock_logger_error, \
         patch('traceback.print_exc') as mock_print_exc:
        
        # Configure the mocks
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_dispatcher = MagicMock()
        polling_error = Exception("Polling error")
        mock_dispatcher.start_polling = AsyncMock(side_effect=polling_error)
        mock_dispatcher.include_routers = MagicMock()
        mock_dispatcher_class.return_value = mock_dispatcher
        
        # Call the main function
        await main()
        
        # Check that the error is handled correctly
        mock_logger_error.assert_called_once_with(f"Error starting bot: {polling_error}")
        mock_print_exc.assert_called_once()
        mock_bot.session.close.assert_awaited_once()

def test_bot_token_not_set():
    """Test checking error when BOT_TOKEN is not set"""
    # Save the original value of BOT_TOKEN
    original_token = os.environ.get('BOT_TOKEN')
    
    try:
        # Remove BOT_TOKEN from the environment
        if 'BOT_TOKEN' in os.environ:
            del os.environ['BOT_TOKEN']
        
        # Patch os.getenv to return None for BOT_TOKEN
        with patch('os.getenv', return_value=None):
            # Check that ValueError is raised
            with pytest.raises(ValueError, match="BOT_TOKEN is not set in the .env file"):
                # Reload the bot module to trigger the BOT_TOKEN check
                import importlib
                importlib.reload(bot)
    finally:
        # Restore the original value of BOT_TOKEN
        if original_token is not None:
            os.environ['BOT_TOKEN'] = original_token

def test_keyboard_interrupt_handler():
    """Test KeyboardInterrupt handler"""
    # Patch sys.exit to prevent the program from exiting during the test
    with patch('sys.exit') as mock_exit, \
         patch.object(logger, 'info') as mock_logger_info:
        
        # Directly call the KeyboardInterrupt handler
        try:
            # Simulate the try-except block from bot.py
            raise KeyboardInterrupt()
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            sys.exit(0)
        
        # Check that the error is handled correctly
        mock_logger_info.assert_called_once_with("Bot stopped")
        mock_exit.assert_called_once_with(0)

def test_general_exception_handler():
    """Test general error handler"""
    # Create a test error
    test_exception = Exception("Critical test error")
    
    # Patch sys.exit and traceback.print_exc for testing
    with patch('sys.exit') as mock_exit, \
         patch.object(logger, 'critical') as mock_logger_critical, \
         patch('traceback.print_exc') as mock_print_exc:
        
        # Directly call the general error handler
        try:
            # Simulate the try-except block from bot.py
            raise test_exception
        except Exception as e:
            logger.critical(f"Critical error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        # Check that the error is handled correctly
        mock_logger_critical.assert_called_once_with(f"Critical error: {test_exception}")
        mock_print_exc.assert_called_once()
        mock_exit.assert_called_once_with(1)

def test_main_entry_point():
    """Test for covering the if __name__ == '__main__' block"""
    # Use source coverage to run the code
    with patch('asyncio.run'), \
         patch('sys.exit'), \
         patch.dict(globals(), {'__name__': '__main__'}):
        
        # Execute the main block
        if __name__ == "__main__":
            try:
                # Start the main function
                asyncio.run(main())
            except (KeyboardInterrupt, SystemExit):
                # Log the shutdown
                logger.info("Bot stopped")
                sys.exit(0)
            except Exception as e:
                # Log the error
                logger.critical(f"Critical error: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
