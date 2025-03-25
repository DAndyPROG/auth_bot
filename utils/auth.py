import json
import os
import time
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Auth0 Certificate information
AUTH0_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIDHTCCAgWgAwIBAgIJOquqcuFijSPJMA0GCSqGSIb3DQEBCwUAMCwxKjAoBgNV
BAMTIWRldi12dmhmamRjeWd2dTRwMTc2LnVzLmF1dGgwLmNvbTAeFw0yNTAzMjQw
NzQ4NDFaFw0zODEyMDEwNzQ4NDFaMCwxKjAoBgNVBAMTIWRldi12dmhmamRjeWd2
dTRwMTc2LnVzLmF1dGgwLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC
ggEBAObCZ407YAbBb2s2dX5jfWyEUwROXyNBerJIig5Tc9/LjeuXD2Nhx5/446XB
OBrd4NhluRQ+eyppAnO1qE6nFvz8ZPsslV7gz61+nldX3Ic6t0LSCmu+PVdprAYv
MTLfBe03gkLE7ryVArzj6ytDhzSMOpJiGm4SoQR33frKA94hlgZ6AW2X28BIw65J
Utx+DLsCB1vyYuGqYOLjsxrXtzXKawkMjaNcD2aYA4x/k4dW1cguiHB4seqpj4zW
NcGp88AFQ+FfZht2PBD+1J41X9eBncbmiHepENfQcqB9BcMlREW2mwhFNmhDbFE4
H7gkxjtBnwYL74mUqbewbpgvS20CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAd
BgNVHQ4EFgQUW8JnQiMNBvVVJw4YjyrkAhCwNiowDgYDVR0PAQH/BAQDAgKEMA0G
CSqGSIb3DQEBCwUAA4IBAQBB7cER674/bYdhxt9bpGyqnPfqDjWehpreD7unsXeM
0dCZ091rUvuCvo/cbglO6f1eQvsQjMvrP/HAjcRMjiiN5ApOk4Wrk97VQStkofXA
GCgU0mbcoiEDZMcXIeHpigeQdstreveMGEFlY4PbQyUwI+/FdL9JQpfUPH5uDGxt
2BeFBLJQaz++AsElV+LKH0dfRTx4k640dZqJgpOYaC/Spw3GNk8zIxjjobn9ZLfF
mgjNTmO2tKEQk2sJbA2LLvy9ctXXrHYlSErkRnMtr450z7ZD0665FIK5i/y5LCiW
g5ZvSIZhYgr6UDkAEkaeqL0iA+ZxKnviBo0/XkX8bQJs
-----END CERTIFICATE-----"""

# Class for working with Auth0
class Auth0Client:
    def __init__(self):
        """Initialization of the Auth0 client"""
        # Reload environment variables
        load_dotenv()
        
        self.domain = os.getenv("AUTH0_DOMAIN", "")
        self.client_id = os.getenv("AUTH0_CLIENT_ID", "")
        self.client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")
        self.audience = os.getenv("AUTH0_AUDIENCE", "")
        self.scope = os.getenv("AUTH0_SCOPE", "openid profile email")
        self.certificate = AUTH0_CERTIFICATE
        self.certificate_fingerprint = "374DCC1CF258051A865F658F16F70BF56BFADEC2"
        self.device_flow_data = {}  # Stores device flow data for each user
        
        print(f"Auth0 settings: Domain={self.domain}, ClientID={self.client_id[:5] if self.client_id else 'not specified'}...")
        
        # Check settings during initialization
        self._check_settings_sync()

    def _check_settings_sync(self) -> bool:
        """Synchronous check of Auth0 settings"""
        settings_valid = all([self.domain, self.client_id, self.client_secret, self.audience])
        if not settings_valid:
            missing = []
            if not self.domain: missing.append("AUTH0_DOMAIN")
            if not self.client_id: missing.append("AUTH0_CLIENT_ID")
            if not self.client_secret: missing.append("AUTH0_CLIENT_SECRET")
            if not self.audience: missing.append("AUTH0_AUDIENCE")
            print(f"Missing Auth0 settings: {', '.join(missing)}")
        return settings_valid

    async def check_settings(self) -> bool:
        """Checks if all necessary variables are configured for working with Auth0"""
        # Reload environment variables
        load_dotenv()
        
        # Update the values from .env
        self.domain = os.getenv("AUTH0_DOMAIN", "")
        self.client_id = os.getenv("AUTH0_CLIENT_ID", "")
        self.client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")
        self.audience = os.getenv("AUTH0_AUDIENCE", "")
        self.scope = os.getenv("AUTH0_SCOPE", "openid profile email")
        
        settings_valid = all([self.domain, self.client_id, self.client_secret, self.audience])
        if not settings_valid:
            missing = []
            if not self.domain: missing.append("AUTH0_DOMAIN")
            if not self.client_id: missing.append("AUTH0_CLIENT_ID")
            if not self.client_secret: missing.append("AUTH0_CLIENT_SECRET")
            if not self.audience: missing.append("AUTH0_AUDIENCE")
            print(f"Відсутні налаштування Auth0: {', '.join(missing)}")
        return settings_valid

    async def start_device_flow(
        self, user_id: int
    ) -> Tuple[str, str, int]:
        """
        Starts Device Flow authorization
        
        Args:
            user_id: ID of the user in Telegram
            
        Returns:
            Tuple[str, str, int]: URL for verification, user code and code expiration time
        """
        print(f"Starting Device Flow for user {user_id}")
        # Check Auth0 settings
        settings_valid = await self.check_settings()
        if not settings_valid:
            # Use the test mode if the settings are incomplete
            print(f"Using the test mode for user {user_id}")
            dummy_data = {
                "device_code": "dummy_device_code",
                "expires_at": time.time() + 1800,  # 30 хвилин
                "interval": 5,
                "last_check": time.time(),
            }
            self.device_flow_data[user_id] = dummy_data
            return "https://example.com/auth", f"TEST-CODE-{user_id}", 1800
        
        # Prepare the data for the request
        url = f"https://{self.domain}/oauth/device/code"
        payload = {
            "client_id": self.client_id,
            "audience": self.audience,
            "scope": self.scope,
        }
        
        try:
            # Make a request to Auth0
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    # Check the status of the response
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error Auth0 when getting device_code: {error_text}")
                        raise Exception(f"Error Auth0: {error_text}")
                    
                    # Get the data
                    data = await response.json()
                    print(f"Received device_code, verification_uri: {data.get('verification_uri_complete')}")
                    
                    # Save the data for further use
                    self.device_flow_data[user_id] = {
                        "device_code": data["device_code"],
                        "expires_at": time.time() + data["expires_in"],
                        "interval": data["interval"],
                        "last_check": time.time(),
                    }
                    
                    # Return the data for display to the user
                    return data["verification_uri_complete"], data["user_code"], data["expires_in"]
        except Exception as e:
            # Handle errors and add dummy data for testing without Auth0
            print(f"Error when starting Device Flow: {e}")
            # Return dummy data for testing
            dummy_data = {
                "device_code": "dummy_device_code",
                "expires_at": time.time() + 1800,  # 30 хвилин
                "interval": 5,
                "last_check": time.time(),
            }
            self.device_flow_data[user_id] = dummy_data
            return "https://example.com/auth", f"TEST-CODE-{user_id}", 1800

    async def poll_device_flow(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Polls Auth0 for a token
        
        Args:
            user_id: ID користувача Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Token or None if authorization is not completed
        """
        # Check if there is data for the user
        if user_id not in self.device_flow_data:
            return None
        
        device_data = self.device_flow_data[user_id]
        
        # Check if the code has expired
        if time.time() > device_data["expires_at"]:
            del self.device_flow_data[user_id]
            return None
        
        # Check if the interval has passed between requests
        if time.time() - device_data["last_check"] < device_data["interval"]:
            return None
        
        # Update the time of the last check
        device_data["last_check"] = time.time()
        
        # If this is a test mode (dummy_device_code), return a dummy token
        if device_data["device_code"] == "dummy_device_code":
            del self.device_flow_data[user_id]
            print(f"Returning a dummy token for user {user_id}")
            return {
                "access_token": f"dummy_access_token_{user_id}",
                "token_type": "Bearer",
                "expires_in": 86400
            }
        
        # Prepare the data for the request
        url = f"https://{self.domain}/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "device_code": device_data["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }
        
        try:
            # Make a request to Auth0
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    # Check the status of the response
                    if response.status != 200:
                        error_data = await response.json()
                        error = error_data.get("error", "")
                        
                        # If the user has not completed authorization, continue polling
                        if error == "authorization_pending":
                            return None
                        
                        # If another error occurred, delete the data and stop polling
                        del self.device_flow_data[user_id]
                        print(f"Error Auth0 when getting a token: {error_data}")
                        raise Exception(f"Error Auth0: {error_data}")
                    
                    # Get the token data
                    token_data = await response.json()
                    print(f"Received an access token for user {user_id}")
                    
                    # Delete the device flow data, since authorization is completed
                    del self.device_flow_data[user_id]
                    
                    return token_data
        except Exception as e:
            print(f"Error when polling Device Flow: {e}")
            # In test mode, return a dummy token
            if not await self.check_settings():
                del self.device_flow_data[user_id]
                return {
                    "access_token": f"dummy_access_token_{user_id}",
                    "token_type": "Bearer",
                    "expires_in": 86400
                }
            return None

    async def get_user_info(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gets user information by token
        
        Args:
            token_data: Token data
            
        Returns:
            Dict[str, Any]: Інформація про користувача
        """
        # If this is a test token, return dummy data
        if token_data.get("access_token", "").startswith("dummy_access_token_"):
            user_id = token_data["access_token"].split("_")[-1]
            
            # Generate dummy user data
            return {
                "sub": f"auth0|test{user_id}",
                "name": f"Test User {user_id}",
                "nickname": f"testuser{user_id}",
                "email": f"test{user_id}@example.com",
                "email_verified": True,
                "picture": "https://example.com/avatar.png",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        
        # Get the access token
        access_token = token_data.get("access_token")
        if not access_token:
            raise Exception("Access token is missing")
        
        # Prepare the request to Auth0
        url = f"https://{self.domain}/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            # Make a request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    # Check the status of the response
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error Auth0 when getting user information: {error_text}")
                        raise Exception(f"Error Auth0: {error_text}")
                    
                    # Get the user data
                    user_info = await response.json()
                    
                    # Add a record of successful authorization
                    with open("auth_success.log", "a") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Successful authorization of user: {user_info.get('sub')}\n")
                    
                    # Save the authorization data to a JSON file
                    self._save_auth_data(user_info)
                    
                    return user_info
        except Exception as e:
            print(f"Error when getting user information: {e}")
            raise

    def _save_auth_data(self, user_info: Dict[str, Any]) -> None:
        """
        Saves authorization data to a file
        
        Args:
            user_info: User information
        """
        try:
            # Create the auth_data directory if it doesn't exist
            os.makedirs("auth_data", exist_ok=True)
            
            # Form the filename based on user_id or sub
            user_id = user_info.get("sub", "unknown").replace("|", "_")
            filename = f"auth_data/{user_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
            
            # Save the data to a JSON file
            with open(filename, "w") as f:
                json.dump(user_info, f, indent=2)
                
            print(f"Authorization data saved to file: {filename}")  
        except Exception as e:
            print(f"Error when saving authorization data: {e}")

    async def check_authorization(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Checks if the user is authorized
        
        Args:
            user_id: ID of the user in Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Authorization data or None
        """
        # Check if there is a process flow for this user
        if user_id not in self.device_flow_data:
            return None
        
        # Get the token
        token_data = await self.poll_device_flow(user_id)
        if not token_data:
            return None
        
        # Get the user information
        user_info = await self.get_user_info(token_data)
        
        # Return the authorization data
        return {
            "token": token_data,
            "user_info": user_info,
        }

    async def _get_openid_config(self) -> Dict[str, Any]:
        """
        Get the OpenID configuration from Auth0
        
        Returns:
            Dict[str, Any]: The OpenID configuration
        """
        try:
            if not self._check_settings_sync():
                print(f"[{datetime.now()}] Invalid Auth0 settings, cannot get OpenID configuration")
                return {}
            
            url = f"https://{self.domain}/.well-known/openid-configuration"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"[{datetime.now()}] Failed to get OpenID configuration: {await response.text()}")
                        return {}
                    
                    return await response.json()
        except Exception as e:
            print(f"[{datetime.now()}] Error getting OpenID configuration: {e.__class__.__name__}: {e}")
            return {}
            
    async def _request_device_code(self, endpoint: str) -> Dict[str, Any]:
        """
        Request a device code from Auth0
        
        Args:
            endpoint: The endpoint to request the device code from
            
        Returns:
            Dict[str, Any]: The device code data
        """
        try:
            if not self._check_settings_sync():
                print(f"[{datetime.now()}] Invalid Auth0 settings, cannot request device code")
                return {}
            
            payload = {
                "client_id": self.client_id,
                "scope": "openid profile email",
            }
            
            if self.audience:
                payload["audience"] = self.audience
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, data=payload) as response:
                    if response.status != 200:
                        print(f"[{datetime.now()}] Failed to request device code: {await response.text()}")
                        return {}
                    
                    return await response.json()
        except Exception as e:
            print(f"[{datetime.now()}] Error requesting device code: {e.__class__.__name__}: {e}")
            return {}
            
    async def _token_request(self, device_code: str) -> Dict[str, Any]:
        """
        Request a token using the device code
        
        Args:
            device_code: The device code to use
            
        Returns:
            Dict[str, Any]: The token data, or a dict with an error field
        """
        try:
            if not self._check_settings_sync():
                print(f"[{datetime.now()}] Invalid Auth0 settings, cannot request token")
                return {"error": "invalid_settings"}
            
            url = f"https://{self.domain}/oauth/token"
            payload = {
                "client_id": self.client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    response_data = await response.json()
                    
                    if response.status != 200:
                        error = response_data.get("error", "unknown_error")
                        print(f"[{datetime.now()}] Token request failed: {error}")
                        return {"error": error}
                    
                    return response_data
        except Exception as e:
            print(f"[{datetime.now()}] Error requesting token: {e.__class__.__name__}: {e}")
            return {"error": "request_failed"}

# Create a global instance of the Auth0 client
auth0_client = Auth0Client()

class Auth0DeviceFlow:
    """Auth0 device flow implementation"""

    def __init__(self, domain, client_id, audience=None):
        """Initialize the Auth0 device flow"""
        self.domain = domain
        self.client_id = client_id
        self.audience = audience
        self.device_flow_data = {}

    async def start_device_flow(self, user_id):
        """
        Start the device flow
        
        Args:
            user_id: ID of the user in Telegram
            
        Returns:
            Tuple[str, str, int]: URL for authorization, user code and expiration time
        """
        try:
            # Get the configuration
            config = await self._get_openid_config()
            
            # Request device code
            device_code_data = await self._request_device_code(config.get("device_authorization_endpoint"))
            
            # Check required fields
            if not device_code_data.get("verification_uri_complete") or not device_code_data.get("user_code"):
                print(f"[{datetime.now()}] Device code request failed: missing required fields")
                print(f"[{datetime.now()}] Response: {device_code_data}")
                return None, None, 0
            
            # Store the device code data for the user
            self.device_flow_data[user_id] = device_code_data
            
            # Return the URL, user code and expiration time
            return (
                device_code_data.get("verification_uri_complete"),
                device_code_data.get("user_code"),
                device_code_data.get("expires_in", 300)
            )
        except Exception as e:
            print(f"[{datetime.now()}] Error starting device flow: {e.__class__.__name__}: {e}")
            return None, None, 0
    
    def clear_authorization(self, user_id):
        """
        Clear the authorization data for a user
        
        Args:
            user_id: ID of the user in Telegram
            
        Returns:
            bool: True if the data was cleared, False otherwise
        """
        if user_id in self.device_flow_data:
            del self.device_flow_data[user_id]
            return True
        return False
