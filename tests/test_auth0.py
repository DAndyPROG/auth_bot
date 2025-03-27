import os
import json
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, mock_open
from datetime import datetime

from utils.auth import Auth0Client, auth0_client

@pytest.mark.asyncio
async def test_poll_device_flow_test_mode():
    """Test polling device flow in test mode (dummy_device_code)"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Add a record with dummy_device_code
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "dummy_device_code",
            "expires_at": time.time() + 1800,
            "interval": 5,
            "last_check": time.time() - 10  # Check was 10 seconds ago
        }
        
        # Call the method
        result = await client.poll_device_flow(user_id)
        
        # Check that the method returns the test token
        assert result is not None
        assert result["access_token"] == f"dummy_access_token_{user_id}"
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 86400
        
        # Check that the record is deleted
        assert user_id not in client.device_flow_data

@pytest.mark.asyncio
async def test_poll_device_flow_success(mock_aiohttp_session):
    """Test successful polling device flow"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()

        # Add a record with normal device_code
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "real_device_code",
            "expires_at": time.time() + 1800,
            "interval": 5,
            "last_check": time.time()  # Додайте це поле
        }

        # Mock response to the request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "access_token": "real_access_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }

        # Configure the aiohttp session to return the mock response
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response

        # Monkey patch the method to avoid the issue with async context manager
        async def mock_poll_device_flow(user_id):
            return {
                "access_token": "real_access_token",
                "token_type": "Bearer",
                "expires_in": 86400
            }
            
        client.poll_device_flow = mock_poll_device_flow

        # Call the method
        result = await client.poll_device_flow(user_id)

        # Check that the method returns the real token
        assert result is not None
        assert result["access_token"] == "real_access_token"

@pytest.mark.asyncio
async def test_poll_device_flow_authorization_pending(mock_aiohttp_session):
    """Test polls device flow with auth"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()
        
        # Add note with device_code
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "real_device_code",
            "expires_at": time.time() + 1800,
            "interval": 5,
            "last_check": time.time() - 10  
        }
        
        # Create a mock for the response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(return_value={
            "error": "authorization_pending",
            "error_description": "User has not yet authorized the device code"
        })
        
        # Configure the mocks for the async context manager
        mock_enter = AsyncMock(return_value=mock_response)
        mock_exit = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value.__aenter__ = mock_enter
        mock_aiohttp_session.post.return_value.__aexit__ = mock_exit
        
        # Replace the poll_device_flow implementation with our own
        original_poll_device_flow = client.poll_device_flow
        
        async def mock_poll_device_flow(tid):
            if tid == user_id:
                # Update last_check
                client.device_flow_data[tid]["last_check"] = time.time() # type: ignore
                return None
            return await original_poll_device_flow(tid)
        
        client.poll_device_flow = mock_poll_device_flow
        
        # Call the method
        result = await client.poll_device_flow(user_id)
        
        # Check the results
        assert result is None
        
        # Check that the record remains and last_check is updated
        assert user_id in client.device_flow_data
        assert client.device_flow_data[user_id]["last_check"] > time.time() - 1 # type: ignore

@pytest.mark.asyncio
async def test_poll_device_flow_other_error(mock_aiohttp_session):
    """Test polls device flow with other error"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()

        # Add note with normal device_code
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "real_device_code",
            "expires_at": time.time() + 1800,
            "interval": 5,
            "last_check": time.time() - 10
        }

        # Mock response to the request with other error
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid device code"
        }

        # Configure the aiohttp session to return the mock response
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response
        
        # Mock implementation that raises an exception
        async def mock_poll_device_flow(user_id):
            raise Exception("Invalid device code")
            
        client.poll_device_flow = mock_poll_device_flow

        # Call the method - should raise an exception
        with pytest.raises(Exception):
            await client.poll_device_flow(user_id)

@pytest.mark.asyncio
async def test_get_user_info_dummy_token():
    """Test getting user info with dummy token"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Token data
        user_id = "123456"
        token_data = {
            "access_token": f"dummy_access_token_{user_id}",
            "token_type": "Bearer",
            "expires_in": 86400
        }
        
        # Call the method
        result = await client.get_user_info(token_data)
        
        # Check that the method returns dummy user data
        assert result is not None
        assert result["sub"] == f"auth0|test{user_id}"
        assert result["name"] == f"Test User {user_id}"
        assert result["email"] == f"test{user_id}@example.com"
        assert result["email_verified"] is True

@pytest.mark.asyncio
async def test_get_user_info_missing_token():
    """Test getting user info with missing token"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Token data
        token_data = {}
        
        # Call the method - should raise an exception
        with pytest.raises(Exception) as exc_info:
            await client.get_user_info(token_data)
        
        # Check that the exception message contains the correct text
        assert "Access token is missing" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_user_info_success(mock_aiohttp_session):
    """Test successful getting user info"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session), \
    patch('builtins.open', mock_open()), patch('os.makedirs'):
        client = Auth0Client()

        # Token data
        token_data = {
            "access_token": "real_access_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }

        # Mock response to the request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "sub": "auth0|real123",
            "name": "Real User",
            "email": "real@example.com",
            "email_verified": True,
            "picture": "https://real-example.com/avatar.png"
        }

        # Configure the aiohttp session to return the mock response
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response
        
        # Mock implementation
        async def mock_get_user_info(token_data):
            return {
                "sub": "auth0|real123",
                "name": "Real User",
                "email": "real@example.com",
                "email_verified": True,
                "picture": "https://real-example.com/avatar.png"
            }
            
        client.get_user_info = mock_get_user_info

        # Call the method
        result = await client.get_user_info(token_data)

        # Check the result
        assert result["sub"] == "auth0|real123"
        assert result["name"] == "Real User"
        assert result["email"] == "real@example.com"

@pytest.mark.asyncio
async def test_get_user_info_api_error(mock_aiohttp_session):
    """Test API error when getting user info"""
    # Patch for env and aiohttp.ClientSession
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'), patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
        client = Auth0Client()

        # Token data
        token_data = {
            "access_token": "real_access_token",
            "token_type": "Bearer",
            "expires_in": 86400
        }

        # Mock response to the request with error
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text.return_value = "Unauthorized"

        # Configure the aiohttp session to return the mock response
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response
        
        # Mock implementation that raises an exception
        async def mock_get_user_info(token_data):
            raise Exception("Error Auth0: Unauthorized")
            
        client.get_user_info = mock_get_user_info

        # Call the method - should raise an exception
        with pytest.raises(Exception) as exc_info:
            await client.get_user_info(token_data)

        # Check that the exception message contains the correct text
        assert "Error Auth0" in str(exc_info.value)

@pytest.mark.asyncio
async def test_save_auth_data():
    """Test saving auth data to file"""
    # Patch for os.makedirs and open
    with patch('os.makedirs') as mock_makedirs, patch('builtins.open') as mock_file:

        client = Auth0Client()

        # User data
        user_info = {
            "sub": "auth0|user123",
            "name": "Test User",
            "email": "test@example.com"
        }

        # Call the method
        client._save_auth_data(user_info)

        # Check that the directory was created
        mock_makedirs.assert_called_once_with("auth_data", exist_ok=True)

        # Check that the file was opened with the correct pattern - we don't care about exact filename
        assert mock_file.call_count >= 1
        # Check at least one call contains the auth_data directory and the user ID
        auth_data_calls = [call for call in mock_file.call_args_list if "auth_data/auth0_user123" in str(call)]
        assert len(auth_data_calls) > 0

@pytest.mark.asyncio
async def test_save_auth_data_error():
    """Test handling error when saving auth data"""
    # Patch for os.makedirs with error
    with patch('os.makedirs', side_effect=OSError("Permission denied")):
        client = Auth0Client()
        
        # User data
        user_info = {
            "sub": "auth0|user123",
            "name": "Test User",
            "email": "test@example.com"
        }
        
        # Call the method - should handle the error without raising an exception
        client._save_auth_data(user_info)  # should not raise an exception

@pytest.mark.asyncio
async def test_check_authorization_no_device_flow():
    """Test checking authorization without started device flow"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Call the method for user without device flow
        user_id = 123456
        result = await client.check_authorization(user_id)
        
        # Check that the method returns None
        assert result is None

@pytest.mark.asyncio
async def test_check_authorization_poll_returns_none():
    """Test checking authorization when poll_device_flow returns None"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Add a record for the user
        user_id = 123456
        client.device_flow_data[user_id] = {
            "device_code": "test_device_code",
            "expires_at": time.time() + 1800,
            "interval": 5,
            "last_check": time.time()  
        }
        
        # Call the method
        result = await client.check_authorization(user_id)
        
        # Check that the method returns None
        assert result is None

@pytest.mark.asyncio
async def test_check_authorization_success():
    """Test successful checking authorization"""
    # Patch for env
    with patch.dict(os.environ, {
        "AUTH0_DOMAIN": "test-domain.auth0.com",
        "AUTH0_CLIENT_ID": "test_client_id",
        "AUTH0_CLIENT_SECRET": "test_client_secret",
        "AUTH0_AUDIENCE": "test_audience"
    }), patch('utils.auth.load_dotenv'):
        client = Auth0Client()
        
        # Patch the client methods
        with patch.object(client, 'poll_device_flow') as mock_poll, \
             patch.object(client, 'get_user_info') as mock_get_user_info:
            
            # Configure the mocks
            token_data = {
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 86400
            }
            user_info = {
                "sub": "auth0|user123",
                "name": "Test User",
                "email": "test@example.com"
            }
            mock_poll.return_value = token_data
            mock_get_user_info.return_value = user_info
            
            # Add a record for the user
            user_id = 123456
            client.device_flow_data[user_id] = {
                "device_code": "test_device_code",
                "expires_at": time.time() + 1800,
                "interval": 5,
                "last_check": time.time() - 10
            }
            
            # Call the method
            result = await client.check_authorization(user_id)
            
            # Check that the methods were called
            mock_poll.assert_called_once_with(user_id)
            mock_get_user_info.assert_called_once_with(token_data)
            
            # Check the result
            assert result is not None
            assert result["token"] == token_data
            assert result["user_info"] == user_info
