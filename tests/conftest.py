import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from utils.database import Base, AsyncDatabase
from utils.auth import Auth0Client
from utils.session import SessionManager

# Fix for event_loop, required for asynchronous tests
# @pytest_asyncio.fixture(scope="function")
# def event_loop():
#     """Create an instance of the default event loop for each test case."""
#     policy = asyncio.get_event_loop_policy()
#     loop = policy.new_event_loop()
#     asyncio.set_event_loop(loop)
#     yield loop
#     # Закриваємо всі таски перед закриттям loop
#     pending = asyncio.all_tasks(loop)
#     for task in pending:
#         task.cancel()
#     loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
#     loop.run_until_complete(loop.shutdown_asyncgens())
#     loop.close()

# Async test database fixture
@pytest_asyncio.fixture
async def in_memory_db():
    """Create an in-memory SQLite database for testing"""
    # Create a new database URL for testing
    test_db_url = "sqlite+aiosqlite:///:memory:"
    
    # Create a new engine
    engine = create_async_engine(test_db_url, echo=False, poolclass=StaticPool)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Close the engine
    await engine.dispose()

@asynccontextmanager
async def get_session(engine):
    """Get a database session."""
    async_session = async_sessionmaker(
        engine, expire_on_commit=False
    )
    session = async_session()
    try:
        yield session
        await session.rollback()
    finally:
        await session.close()

@pytest_asyncio.fixture
async def db_session(in_memory_db):
    """Create a database session for testing"""
    async_session = async_sessionmaker(
        bind=in_memory_db,
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session

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
    
    # Configure the mock for post
    mock_post_response = AsyncMock()
    mock_post_response.status = 200
    mock_post_response.json.return_value = {
        "device_code": "test_device_code",
        "user_code": "TEST-CODE",
        "verification_uri": "https://example.com/verify",
        "verification_uri_complete": "https://example.com/verify?user_code=TEST-CODE",
        "expires_in": 1800,
        "interval": 5
    }
    mock_post_response.__aenter__.return_value = mock_post_response
    
    # Configure the mock for get
    mock_get_response = AsyncMock()
    mock_get_response.status = 200
    mock_get_response.json.return_value = {
        "sub": "auth0|test123",
        "name": "Test User",
        "email": "test@example.com",
        "email_verified": True
    }
    mock_get_response.__aenter__.return_value = mock_get_response
    
    # Set up the session methods
    mock_session.post.return_value = mock_post_response
    mock_session.get.return_value = mock_get_response
    
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
    
    # save current state for possible getting through get_state
    current_state = [None]  # use list for mutability
    
    # redefine async methods for working with state
    async def mock_set_state(new_state):
        current_state[0] = new_state
    
    async def mock_get_state():
        return current_state[0]
    
    async def mock_clear():
        current_state[0] = None
    
    # set mock behavior
    state.set_state.side_effect = mock_set_state
    state.get_state.side_effect = mock_get_state
    state.clear.side_effect = mock_clear
    
    # other methods remain as they are
    state.get_data.return_value = {}
    state.set_data.return_value = None
    state.update_data.return_value = None
    
    return state

@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for tests."""
    policy = asyncio.get_event_loop_policy()
    return policy

def pytest_configure(config):
    config.inicfg["asyncio_default_fixture_loop_scope"] = "function" # type: ignore
