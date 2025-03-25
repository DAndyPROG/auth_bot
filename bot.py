import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

from handlers import auth_router
from utils.database import db
from utils.auth import auth0_client
from utils.session import session_manager

# Load environment variables
load_dotenv(override=True)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the .env file")

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot commands
COMMANDS = [
    BotCommand(command="start", description="Start / Login"),
    BotCommand(command="logout", description="Logout"),

]

async def set_bot_commands(bot: Bot):
    try:
        await bot.set_my_commands(COMMANDS)
        logger.info("Bot commands set successfully")
    except TelegramAPIError as e:
        logger.error(f"Error setting bot commands: {e}")
        if "Unauthorized" in str(e):
            logger.error("Invalid bot token. Check BOT_TOKEN in the .env file")
            raise ValueError("Invalid bot token")

async def main():
    # Initialize the database connection
    try:
        await db.init_models()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return
    
    # Initialize the bot and dispatcher
    try:
        session = AiohttpSession()
        bot = Bot(token=BOT_TOKEN, session=session)
        dp = Dispatcher()
        
        # Pass the bot instance to the session manager (important!)
        session_manager.set_bot(bot)
        logger.info(f"Bot set in session manager: {bot}")
        
        # Register routers
        dp.include_routers(auth_router)
        logger.info("Routers registered")
        
        # Set bot commands
        await set_bot_commands(bot)
        
        # Start polling the Telegram server
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        traceback.print_exc()
    finally:
        # Close the bot session
        if 'bot' in locals() and bot:
            logger.info("Closing bot session")
            await bot.session.close()

# Start the bot
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
        traceback.print_exc()
        sys.exit(1)
