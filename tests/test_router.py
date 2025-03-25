import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.filters import Command, StateFilter
import inspect

from handlers.auth import router, AuthStates
from handlers.states import UserForm

def test_router_debug():
    """Test for debugging the structure of handlers in the router"""
    # Get all message handlers
    message_handlers = router.message.handlers
    print(f"Number of message handlers: {len(message_handlers)}")
    
    if len(message_handlers) > 0:
        # Print information about each handler
        for i, handler in enumerate(message_handlers):
            print(f"\nHandler #{i}:")
            print(f"- Type: {type(handler)}")
            print(f"- Filters: {handler.filters}")
            
            # Print information about each filter
            for j, filter in enumerate(handler.filters):
                print(f"  - Filter #{j}:")
                print(f"    - Type: {type(filter)}")
                
                # If this is a Command, print the commands
                if hasattr(filter, 'commands'):
                    print(f"    - Commands: {filter.commands}")
                
                # If this is a StateFilter, print the states
                if hasattr(filter, 'states'):
                    print(f"    - States: {filter.states}")
                
                # Print all attributes of the filter
                print(f"    - Attributes: {dir(filter)}")
    else:
        print("No message handlers found")
    
    # Check the routes of the router
    print("\nRoutes of the router:")
    for route in dir(router):
        if not route.startswith('_'):
            print(f"- {route}")

def get_filter_class(filter_obj):
    """Getting the filter class from FilterObject"""
    if hasattr(filter_obj, 'callback'):
        return filter_obj.callback.__class__
    return None

def test_router_has_required_handlers():
    """Test checking the presence of required handlers in the router"""
    
    # Get all message handlers
    message_handlers = router.message.handlers
    assert len(message_handlers) > 0, "The router has no message handlers"
    
    # Find the handler for the /start command
    start_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == Command and hasattr(filter_obj.callback, 'commands') and 'start' in filter_obj.callback.commands:
                start_handler_found = True
                break
        if start_handler_found:
            break
    assert start_handler_found, "The handler for the /start command was not found"
    
    # Find the handler for the /logout command
    logout_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == Command and hasattr(filter_obj.callback, 'commands') and 'logout' in filter_obj.callback.commands:
                logout_handler_found = True
                break
        if logout_handler_found:
            break
    assert logout_handler_found, "The handler for the /logout command was not found"
    
    # Find the handler for the waiting_for_auth state
    waiting_auth_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == StateFilter and hasattr(filter_obj.callback, 'states') and AuthStates.waiting_for_auth in filter_obj.callback.states:
                waiting_auth_handler_found = True
                break
        if waiting_auth_handler_found:
            break
    assert waiting_auth_handler_found, "The handler for the waiting_for_auth state was not found"
    
    # Find the handler for the authorized state
    authorized_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == StateFilter and hasattr(filter_obj.callback, 'states') and AuthStates.authorized in filter_obj.callback.states:
                authorized_handler_found = True
                break
        if authorized_handler_found:
            break
    assert authorized_handler_found, "The handler for the authorized state was not found"
    
    # Find the handler for the waiting_full_name state
    waiting_name_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == StateFilter and hasattr(filter_obj.callback, 'states') and UserForm.waiting_full_name in filter_obj.callback.states:
                waiting_name_handler_found = True
                break
        if waiting_name_handler_found:
            break
    assert waiting_name_handler_found, "The handler for the waiting_full_name state was not found"
    
    # Find the handler for the waiting_phone state
    waiting_phone_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == StateFilter and hasattr(filter_obj.callback, 'states') and UserForm.waiting_phone in filter_obj.callback.states:
                waiting_phone_handler_found = True
                break
        if waiting_phone_handler_found:
            break
    assert waiting_phone_handler_found, "The handler for the waiting_phone state was not found"
    
    # Find the handler for the waiting_confirmation state
    waiting_confirmation_handler_found = False
    for handler in message_handlers:
        for filter_obj in handler.filters:
            filter_class = get_filter_class(filter_obj)
            if filter_class == StateFilter and hasattr(filter_obj.callback, 'states') and UserForm.waiting_confirmation in filter_obj.callback.states:
                waiting_confirmation_handler_found = True
                break
        if waiting_confirmation_handler_found:
            break
    assert waiting_confirmation_handler_found, "The handler for the waiting_confirmation state was not found" 