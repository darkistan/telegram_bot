from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from constants import CALLBACK_PREFIXES

def create_router_keyboard(router_names: list) -> InlineKeyboardMarkup:
    """Створює клавіатуру для вибору роутера"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for router_name in router_names:
        callback_data = f"{CALLBACK_PREFIXES['router']}{router_name}"
        keyboard.add(InlineKeyboardButton(router_name, callback_data=callback_data))
    
    return keyboard

def create_script_keyboard(router_name: str, scripts: list) -> InlineKeyboardMarkup:
    """Створює клавіатуру для вибору скрипта"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for script in scripts:
        callback_data = f"{CALLBACK_PREFIXES['script']}{router_name}_{script}"
        keyboard.add(InlineKeyboardButton(script, callback_data=callback_data))
    
    return keyboard

def create_empty_keyboard() -> InlineKeyboardMarkup:
    """Створює порожню клавіатуру"""
    return InlineKeyboardMarkup()

def add_button_to_keyboard(keyboard: InlineKeyboardMarkup, text: str, callback_data: str):
    """Додає кнопку до існуючої клавіатури"""
    keyboard.add(InlineKeyboardButton(text, callback_data=callback_data))
    return keyboard

def create_custom_keyboard(buttons: list) -> InlineKeyboardMarkup:
    """Створює клавіатуру з кастомними кнопками
    
    Args:
        buttons: список кортежів (текст, callback_data)
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for text, callback_data in buttons:
        keyboard.add(InlineKeyboardButton(text, callback_data=callback_data))
    
    return keyboard 