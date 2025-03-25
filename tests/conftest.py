import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import NullPool

from utils.database import Base, AsyncDatabase
from utils.auth import Auth0Client
from utils.session import SessionManager

# Fix for event_loop, required for asynchronous tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Async test database fixture
@pytest.fixture
async def async_db():
    """Create an in-memory database for tests."""
    db = AsyncDatabase("sqlite+aiosqlite:///:memory:")
    
    # Create tables
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield db
    
    # Drop tables after use
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Close database connection
    await db.engine.dispose()

# Async database session fixture
@pytest.fixture
async def async_session(async_db):
    """Create an async session for tests."""
    # Create a mock session instead of the real one
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Configure the mock for execute
    mock_execute_result = AsyncMock()
    mock_execute_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_execute_result
    
    # Configure the mock for commit
    mock_session.commit.return_value = None
    
    # Configure the mock for rollback
    mock_session.rollback.return_value = None
    
    yield mock_session
    
    # No need to clean up, as this is a mock

# Mock Auth0Client fixture
@pytest.fixture
def mock_auth0_client():
    """Mock Auth0Client for tests."""
    mock_client = AsyncMock(spec=Auth0Client)
    mock_client.device_flow_data = {}
    
    # Configure the mocks for methods
    mock_client.check_settings.return_value = True
    mock_client._check_settings_sync.return_value = True
    mock_client.start_device_flow.return_value = ("https://example.com/verify", "TEST-CODE", 1800)
    mock_client.poll_device_flow.return_value = {
        "access_token": "dummy_access_token_123",
        "token_type": "Bearer",
        "expires_in": 86400
    }
    mock_client.get_user_info.return_value = {
        "sub": "auth0|test123",
        "name": "Test User",
        "email": "test@example.com",
        "email_verified": True
    }
    
    return mock_client

# Mock session_manager fixture
@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for tests."""
    mock_manager = AsyncMock(spec=SessionManager)
    mock_manager.sessions = {}
    mock_manager.timers = {}
    
    # Configure the mocks for methods
    mock_manager.start_session.return_value = None
    mock_manager.is_authorized.return_value = False
    mock_manager.get_auth_data.return_value = None
    mock_manager.register_activity.return_value = True
    mock_manager.set_authorized.return_value = None
    mock_manager.close_session.return_value = True
    
    return mock_manager

# Mock aiohttp.ClientSession fixture
@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp.ClientSession for tests."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "device_code": "test_device_code",
        "user_code": "TEST-CODE",
        "verification_uri": "https://example.com/verify",
        "verification_uri_complete": "https://example.com/verify?user_code=TEST-CODE",
        "expires_in": 1800,
        "interval": 5
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    return mock_session

# Mock bot fixture
@pytest.fixture
def mock_bot():
    """Mock Bot for tests."""
    bot = AsyncMock()
    bot.send_message.return_value = AsyncMock()
    
    return bot

# Mock message fixture
@pytest.fixture
def mock_message():
    """Mock Message for tests."""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 123456
    message.chat = MagicMock()
    message.chat.id = 654321
    message.text = "/start"
    message.message_id = 1
    message.answer = AsyncMock()
    
    return message

# Mock FSMContext fixture
@pytest.fixture
def mock_state():
    """Mock FSMContext for tests."""
    state = AsyncMock()
    state.get_data.return_value = {}
    state.set_data.return_value = None
    state.update_data.return_value = None
    state.set_state.return_value = None
    state.get_state.return_value = None
    state.clear.return_value = None
    
    return state
