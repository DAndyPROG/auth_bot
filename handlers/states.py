from aiogram.fsm.state import State, StatesGroup

class UserForm(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_confirmation = State() 