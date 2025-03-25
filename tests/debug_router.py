import sys
import os

# Додаємо шлях до проекту в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules
from handlers.auth import router, AuthStates
from handlers.states import UserForm
from aiogram.filters import Command, StateFilter

def debug_router():
    """Debugging the structure of handlers in the router"""
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
    print("\nRouter routes:")
    for route in dir(router):
        if not route.startswith('_'):
            print(f"- {route}")
            if hasattr(router, route) and callable(getattr(router, route)):
                method = getattr(router, route)
                print(f"  - Type: {type(method)}")
                print(f"  - Attributes: {dir(method)}")

if __name__ == "__main__":
    debug_router() 