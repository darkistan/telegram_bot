# Константи для повідомлень
MESSAGES = {
    'start': 'Привіт! Я бот для управління маршрутизаторами.',
    'access_request_sent': 'Ваш запит на доступ відправлено адміністраторам. Очікуйте їх рішення.',
    'select_router': 'Виберіть маршрутизатор:',
    'select_script': 'Виберіть скрипт для {}:',
    'no_access': 'У вас немає доступу до роутерів.',
    'router_not_found': 'Помилка: маршрутизатор не знайдено або у вас немає доступу.',
    'password_prompt': 'Введіть пароль для виконання скрипта \'{}\' на маршрутизаторі {}:',
    'confirmation_prompt': 'Ви дійсно хочете виконати скрипт \'{}\' на маршрутизаторі {}?\n\nВідправте \'так\' для підтвердження або \'ні\' для скасування.',
    'wrong_password': 'Невірний пароль для виконання скрипта. Спробуйте ще раз.',
    'script_result': 'Результат виконання скрипта \'{}\':\n{}',
    'script_success': 'Скрипт \'{}\' виконано успішно!\n\nРезультат:\n{}',
    'script_cancelled': 'Виконання скрипта скасувано користувачем.',
    'invalid_response': 'Будь ласка, відповідайте \'так\' для підтвердження або \'ні\' для скасування.',
    'error_loading_routers': 'Помилка при завантаженні даних про маршрутизатори.',
    'error_router_not_found': 'Помилка: маршрутизатор не знайдено.'
}

# Константи для станів користувача
USER_STATES = {
    'waiting_for_router': 'waiting_for_router',
    'waiting_for_script': 'waiting_for_script',
    'waiting_for_password': 'waiting_for_password',
    'waiting_for_confirmation': 'waiting_for_confirmation'
}

# Константи для callback_data
CALLBACK_PREFIXES = {
    'router': 'router_',
    'script': 'script_'
}

# Константи для підтвердження
CONFIRMATION_ANSWERS = {
    'positive': ['так', 'yes', 'y', '1', 'true'],
    'negative': ['ні', 'no', 'n', '0', 'false']
}

from datetime import datetime

# Константи для адміністративних повідомлень
ADMIN_MESSAGE_TEMPLATE = """🔔 Статус виконання скрипта:

📅 Час: {}
👤 Хто запустив: {}
🌐 Маршрутизатор: {}
🖥 Скрипт: {}"""

# Константи для логування
LOG_MESSAGES = {
    'bot_started': 'Бот запущено.',
    'user_started': 'Користувач {} почав взаємодію з ботом.',
    'user_selected_command': 'Користувач {} вибрав команду /run_script.',
    'routers_loaded': 'Завантажені роутери: {}',
    'user_selected_router': 'Користувач {} вибрав маршрутизатор: {}',
    'user_no_access': 'Користувач {} не має доступу до роутерів.',
    'script_executed': 'Скрипт \'{}\' був виконаний на маршрутизаторі \'{}\' в {}.',
    'script_executed_confirmation': 'Скрипт \'{}\' був виконаний на маршрутизаторі \'{}\' в {} (режим підтвердження).',
    'wrong_password_attempt': 'Користувач {} ввів невірний пароль для скрипта {}.',
    'script_cancelled_by_user': 'Користувач {} скасував виконання скрипта {} на маршрутизаторі {}',
    'notifications_status': 'Повідомлення для ADMIN_{}: {}',
    'script_mode_status': 'Режим запуску скриптів: {}'
}

# Допоміжні функції
def get_user_info(message):
    """Отримує інформацію про користувача з повідомлення"""
    return {
        'id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    }

def format_admin_message(execution_time, username, router_name, script):
    """Форматує повідомлення для адміністраторів"""
    return ADMIN_MESSAGE_TEMPLATE.format(execution_time, username, router_name, script)

def get_current_time():
    """Отримує поточний час у форматі для логування"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def is_positive_confirmation(text):
    """Перевіряє, чи є відповідь позитивним підтвердженням"""
    return text.lower() in CONFIRMATION_ANSWERS['positive']

def is_negative_confirmation(text):
    """Перевіряє, чи є відповідь негативним підтвердженням"""
    return text.lower() in CONFIRMATION_ANSWERS['negative'] 