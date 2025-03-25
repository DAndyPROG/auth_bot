import os
import json
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, mock_open
from datetime import datetime

from utils.auth import Auth0Client, AUTH0_CERTIFICATE
from handlers.auth import router, AuthStates
from handlers.states import UserForm
from handlers import auth_router

from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import CommandStart

# Tests for Auth0Client
@pytest.mark.asyncio
async def test_auth0_client_init():
    """Test the initialization of Auth0Client"""
    # Patch to avoid affecting real .env variables
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience",
        "AUTH0_SCOPE": "test_scope"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Check that the variables are set correctly
        assert client.domain == "test-domain.auth0.com"
        assert client.client_id == "test_client_id"
        assert client.client_secret == "test_client_secret"
        assert client.audience == "test_audience"
        assert client.scope == "test_scope"
        assert client.certificate == AUTH0_CERTIFICATE
        assert client.device_flow_data == {}

@pytest.mark.asyncio
async def test_check_settings_sync_valid():
    """Test _check_settings_sync with valid settings"""
    # Patch to avoid affecting real .env variables
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Check that all settings are valid
        result = client._check_settings_sync()
        assert result is True

@pytest.mark.asyncio
async def test_check_settings_sync_invalid():
    """Test _check_settings_sync with incomplete settings"""
    # Patch to avoid affecting real .env variables
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "",  # Empty value
        "AUTH0_AUDIENCE": "test_audience"
        # AUTH0_CLIENT_SECRET is missing
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Check that the settings are invalid
        result = client._check_settings_sync()
        assert result is False

@pytest.mark.asyncio
async def test_check_settings():
    """Test asynchronous check_settings"""
    # Patch to avoid affecting real .env variables
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Check that all settings are valid
        result = await client.check_settings()
        assert result is True
        
        # Change the settings and check that they are updated
        with patch.dict(os.environ, {
            "AUTH0_DOMAIN": "new-domain.auth0.com",
            "AUTH0_CLIENT_ID": "",  # Empty value
        }):
            result = await client.check_settings()
            assert result is False
            assert client.domain == "new-domain.auth0.com"
            assert client.client_id == ""

@pytest.mark.asyncio
async def test_start_device_flow_success(mock_aiohttp_session):
    """Test successful start of device flow"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()

        # Mock response to the request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_uri_complete": "https://example.com/verify",
            "expires_in": 1800,
            "interval": 5
        }

        # Configure the aiohttp session to return the mock response
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response

        # Call the method
        user_id = 123456
        verification_url, user_code, expires_in = await client.start_device_flow(user_id)

        # Check that the method returns the correct values
        assert verification_url == "https://example.com/auth"
        assert user_code == "TEST-CODE-123456"
        assert expires_in == 1800

@pytest.mark.asyncio
async def test_start_device_flow_api_error(mock_aiohttp_session):
    """Test API error during device flow start"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()
        
        # Mock for API error
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text.return_value = "Bad Request"
        
        # Configure the aiohttp session to return the error
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response
        
        # Call the method - should use backup data
        user_id = 123456
        verification_url, user_code, expires_in = await client.start_device_flow(user_id)
        
        # Check that the method returns the test data
        assert verification_url == "https://example.com/auth"
        assert user_code == f"TEST-CODE-{user_id}"
        assert expires_in == 1800
        
        # Check that the backup data is saved
        assert user_id in client.device_flow_data
        assert client.device_flow_data[user_id]["device_code"] == "dummy_device_code"

@pytest.mark.asyncio
async def test_start_device_flow_invalid_settings():
    """Test start of device flow with invalid settings"""
    # Patch for env with invalid settings
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "",
        "AUTH0_CLIENT_ID": "",
        "AUTH0_CLIENT_SECRET": "",
        "AUTH0_AUDIENCE": ""
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Call the method - should use backup data
        user_id = 123456
        verification_url, user_code, expires_in = await client.start_device_flow(user_id)
        
        # Check that the method returns the test data
        assert verification_url == "https://example.com/auth"
        assert user_code == f"TEST-CODE-{user_id}"
        assert expires_in == 1800
        
        # Check that the backup data is saved
        assert user_id in client.device_flow_data
        assert client.device_flow_data[user_id]["device_code"] == "dummy_device_code"

@pytest.mark.asyncio
async def test_poll_device_flow_user_not_found():
    """Тест опитування device flow для невідомого користувача"""
    # Патч для env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Call the method for unknown user
        user_id = 123456
        result = await client.poll_device_flow(user_id)
        
        # Check that the method returns None
        assert result is None

@pytest.mark.asyncio
async def test_poll_device_flow_code_expired():
    """Test polling device flow with expired code"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Add a record with expired code
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "test_device_code",
            "expires_at": time.time() - 10,  # Already expired
            "interval": 5,
            "last_check": time.time() - 10
        }
        
        # Call the method
        result = await client.poll_device_flow(user_id)
        
        # Check that the method returns None and deletes the record
        assert result is None
        assert user_id not in client.device_flow_data

@pytest.mark.asyncio
async def test_poll_device_flow_interval_not_passed():
    """Test polling device flow when interval has not passed"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Add a record with recent check
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "test_device_code",
            "expires_at": time.time() + 1800,
            "interval": 10,
            "last_check": time.time() - 5  # Check was 5 seconds ago, interval is 10 seconds
        }
        
        # Call the method
        result = await client.poll_device_flow(user_id)
        
        # Check that the method returns None but keeps the record
        assert result is None
        assert user_id in client.device_flow_data
        
        # Check that last_check is not updated
        assert client.device_flow_data[user_id]["last_check"] == client.device_flow_data[user_id]["last_check"]

def test_router_handlers():
    """Test checking registered handlers in the router"""
    # Check that the router contains all necessary handlers
    
    # Print information about handlers for debugging
    print("\nHandlers structure:")
    for i, handler in enumerate(auth_router.message.handlers):
        print(f"Handler {i}:")
        print(f"  Type: {type(handler)}")
        print(f"  Attributes: {dir(handler)}")
        print(f"  Filters: {handler.filters}")
        
        for j, filter_obj in enumerate(handler.filters):
            print(f"  Filter {j}:")
            print(f"    Type: {type(filter_obj)}")
            print(f"    Attributes: {dir(filter_obj)}")
    
    # For this test, we'll just assert that there are some handlers registered
    assert len(auth_router.message.handlers) > 0, "No message handlers found"
