import logging
import telebot
from datetime import datetime
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, SCRIPT_PASSWORD_MODE
from fabric import Connection
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError

# Імпорт нових модулів
from constants import MESSAGES, USER_STATES, LOG_MESSAGES, ACCESS_ACTIONS, get_user_info, get_current_time, is_positive_confirmation, is_negative_confirmation
from router_manager import RouterManager
from user_state_manager import UserStateManager
from admin_notifier import AdminNotifier
from keyboard_utils import create_router_keyboard, create_script_keyboard
from access_manager import AccessManager

# Налаштуємо логування з ротацією
from logging.handlers import RotatingFileHandler

# Встановлюємо параметри логування
log_handler = RotatingFileHandler('logs/bot.log', maxBytes=10 * 1024 * 1024, backupCount=5)
log_handler.setLevel(logging.INFO)  # Встановлюємо рівень логування
formatter = logging.Formatter('%(asctime)s - %(message)s')
log_handler.setFormatter(formatter)

# Додаємо обробник в кореневий логер
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

# Створюємо окремий логер для спроб доступу
access_logger = logging.getLogger('access_attempts')
access_logger.setLevel(logging.INFO)
access_logger.propagate = False  # Не передаємо логи в кореневий логер

# Створюємо обробник для логу файлу спроб доступу
access_handler = RotatingFileHandler('logs/access_attempts.log', maxBytes=5 * 1024 * 1024, backupCount=3)
access_handler.setLevel(logging.INFO)
access_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
access_handler.setFormatter(access_formatter)

# Додаємо обробник до логера спроб доступу
access_logger.addHandler(access_handler)

def log_access_attempt(user_id, username, action, result, details=""):
    """
    Логує спробу доступу користувача
    
    :param user_id: ID користувача
    :param username: Ім'я користувача
    :param action: Дія, яку намагався виконати користувач
    :param result: Результат спроби (SUCCESS/FAILED/BLOCKED)
    :param details: Додаткові деталі
    """
    user_info = f"ID: {user_id}"
    if username:
        user_info += f" | Username: @{username}"
    
    log_message = f"ACCESS_ATTEMPT | {user_info} | Action: {action} | Result: {result}"
    if details:
        log_message += f" | Details: {details}"
    
    access_logger.info(log_message)

# Ініціалізація бота для користувачів
bot = telebot.TeleBot(BOT_TOKEN)

# Ініціалізація менеджерів
router_manager = RouterManager()
user_state_manager = UserStateManager()
admin_notifier = AdminNotifier()
access_manager = AccessManager()

# Клас для роботи з SSH через Fabric
class RouterSSHClient:
    def __init__(self, ip: str, username: str, ssh_password: str, ssh_port: int = 22):
        """
        Ініціалізація клієнта SSH.
        
        :param ip: IP-адреса маршрутизатора
        :param username: Ім'я користувача для підключення по SSH
        :param ssh_password: Пароль для підключення по SSH
        :param ssh_port: Порт для підключення по SSH (за замовчуванням 22)
        """
        self.ip = ip
        self.username = username
        self.ssh_password = ssh_password
        self.ssh_port = ssh_port  # Враховуємо порт для SSH

    def execute_script(self, script: str) -> str:
        """
        Виконання скрипта на роутері через SSH.
        
        :param script: Назва скрипта, який потрібно виконати
        :return: Результат виконання скрипта
        """
        try:
            # Створюємо підключення через Fabric
            conn = Connection(
                host=self.ip, 
                user=self.username, 
                connect_kwargs={"password": self.ssh_password},  # Використовуємо ssh_password для SSH-підключення
                port=self.ssh_port  # Вказуємо порт для підключення
            )
            # Виконання скрипта на маршрутизаторі
            result = conn.run(f"/system script run {script}", hide=True)
            return result.stdout
        except AuthenticationException as e:
            logging.error(f"Помилка аутентифікації: {e}")
            return "Помилка аутентифікації. Перевірте правильність пароля SSH."
        except NoValidConnectionsError as e:
            logging.error(f"Помилка з'єднання: {e}")
            return f"Помилка з'єднання. Перевірте доступність маршрутизатора по IP-адресі {self.ip} та порту {self.ssh_port}."
        except SSHException as e:
            logging.error(f"Помилка SSH: {e}")
            return f"Помилка SSH: {e}"
        except Exception as e:
            logging.error(f"Невідома помилка при виконанні скрипта: {e}")
            return f"Невідома помилка при виконанні скрипта: {e}"

# Стан для зберігання даних користувача (замінено на user_state_manager)

# Обробник команди /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, MESSAGES['start'])
    logging.info(LOG_MESSAGES['user_started'].format(message.from_user.username))

# Обробник команди /id для запиту доступу
@bot.message_handler(commands=['id'])
def request_access(message):
    user_info = get_user_info(message)
    
    # Відправляємо повідомлення адміністраторам через оптимізований клас
    admin_notifier.send_access_request_notification(user_info)

    # Підтверджуємо запит користувачу
    bot.reply_to(message, MESSAGES['access_request_sent'])

# Команда для управління доступом (тільки для адміністраторів)
@bot.message_handler(commands=['manage_access'])
def manage_access(message):
    """Обробник команди управління доступом користувачів"""
    # Перевіряємо, чи є користувач адміністратором
    if not access_manager.is_admin(message.from_user.id):
        # Логуємо спробу доступу до забороненої функції
        log_access_attempt(
            message.from_user.id, 
            message.from_user.username, 
            "manage_access", 
            "BLOCKED", 
            "Спроба доступу до управління користувачами"
        )
        bot.reply_to(message, MESSAGES['access_no_permission'])
        return
    
    # Логуємо успішний доступ
    log_access_attempt(
        message.from_user.id, 
        message.from_user.username, 
        "manage_access", 
        "SUCCESS", 
        "Доступ до управління користувачами"
    )
    
    # Створюємо клавіатуру з переліком роутерів
    keyboard = access_manager.create_management_keyboard()
    
    # Отримуємо загальну статистику для заголовка
    routers_info = access_manager.get_all_routers_info()
    total_routers = len(routers_info)
    total_users = sum(info['users_count'] for info in routers_info.values())
    
    header_text = f"🔐 **Управління доступом користувачів**\n\n"
    header_text += f"📊 **Загальна статистика:**\n"
    header_text += f"🌐 Роутерів: {total_routers}\n"
    header_text += f"👥 Користувачів: {total_users}\n\n"
    header_text += f"📋 **Виберіть роутер для редагування користувачів:**"
    
    bot.reply_to(
        message,
        header_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# Відправка вибору маршрутизаторів
@bot.message_handler(commands=['run_script'])
def send_router_selection(message):
    logging.info(LOG_MESSAGES['user_selected_command'].format(message.from_user.username))
    
    # Отримуємо роутери користувача з кешу
    user_routers = router_manager.get_user_routers(message.from_user.id)
    
    if not user_routers:
        # Логуємо спробу доступу без прав
        log_access_attempt(
            message.from_user.id, 
            message.from_user.username, 
            "run_script", 
            "BLOCKED", 
            "Немає доступу до жодного роутера"
        )
        bot.reply_to(message, MESSAGES['no_access'])
        logging.info(LOG_MESSAGES['user_no_access'].format(message.from_user.username))
        return
    
    # Логуємо успішний доступ
    log_access_attempt(
        message.from_user.id, 
        message.from_user.username, 
        "run_script", 
        "SUCCESS", 
        f"Доступ до {len(user_routers)} роутерів"
    )
    
    # Створюємо клавіатуру для вибору роутера
    keyboard = create_router_keyboard(user_routers)
    
    # Відправляємо повідомлення з кнопками вибору маршрутизаторів
    bot.reply_to(message, MESSAGES['select_router'], reply_markup=keyboard)
    user_state_manager.set_waiting_for_router(message.from_user.id)

# Обробка вибору маршрутизатора
@bot.callback_query_handler(func=lambda call: call.data.startswith('router_'))
def handle_router_selection(call):
    router_name = call.data.split('_')[1]  # Беремо ім'я маршрутизатора після 'router_'
    
    # Логуємо вибір маршрутизатора
    logging.info(f"Користувач вибрав маршрутизатор: {router_name}")

    # Перевіряємо доступ користувача до роутера через кеш
    if not router_manager.user_has_access(call.from_user.id, router_name):
        # Логуємо спробу доступу до забороненого роутера
        log_access_attempt(
            call.from_user.id, 
            call.from_user.username, 
            f"access_router_{router_name}", 
            "BLOCKED", 
            f"Спроба доступу до роутера {router_name}"
        )
        bot.send_message(call.message.chat.id, MESSAGES['router_not_found'])
        logging.error(f"Маршрутизатор {router_name} не знайдено або користувач {call.from_user.username} не має доступу.")
        return

    # Логуємо успішний доступ до роутера
    log_access_attempt(
        call.from_user.id, 
        call.from_user.username, 
        f"access_router_{router_name}", 
        "SUCCESS", 
        f"Доступ до роутера {router_name}"
    )
    
    # Логуємо вибір маршрутизатора
    logging.info(LOG_MESSAGES['user_selected_router'].format(call.from_user.username, router_name))

    # Зберігаємо вибраний маршрутизатор
    user_state_manager.set_waiting_for_script(call.from_user.id, router_name)

    # Отримуємо скрипти для роутера з кешу
    scripts = router_manager.get_router_scripts(router_name)
    
    # Створюємо клавіатуру для вибору скрипта
    keyboard = create_script_keyboard(router_name, scripts)

    # Відправляємо повідомлення з кнопками вибору скрипта
    bot.send_message(call.message.chat.id, MESSAGES['select_script'].format(router_name), reply_markup=keyboard)

# Обробка вибору скрипта
@bot.callback_query_handler(func=lambda call: call.data.startswith('script_'))
def handle_script_selection(call):
    router_name, script = call.data.split('_')[1], call.data.split('_')[2]

    if SCRIPT_PASSWORD_MODE:
        # Режим з паролем
        bot.send_message(call.message.chat.id, MESSAGES['password_prompt'].format(script, router_name))
        user_state_manager.set_waiting_for_password(call.from_user.id, router_name, script)
    else:
        # Режим з підтвердженням
        bot.send_message(call.message.chat.id, MESSAGES['confirmation_prompt'].format(script, router_name))
        user_state_manager.set_waiting_for_confirmation(call.from_user.id, router_name, script)

# Перевірка пароля та виконання скрипта
@bot.message_handler(func=lambda message: user_state_manager.is_in_state(message.from_user.id, USER_STATES['waiting_for_password']))
def verify_password_and_execute(message):
    router_name = user_state_manager.get_router_name(message.from_user.id)
    script = user_state_manager.get_script_name(message.from_user.id)

    if not router_name or not script:
        bot.reply_to(message, MESSAGES['error_router_not_found'])
        user_state_manager.clear_user_state(message.from_user.id)
        return

    # Перевіряємо пароль через кеш
    if router_manager.validate_script_password(router_name, message.text):
        execute_script_successfully(message, router_name, script)
    else:
        handle_wrong_password(message, script)

def execute_script_successfully(message, router_name: str, script: str):
    """Виконує скрипт успішно"""
    # Отримуємо інформацію для підключення з кешу
    connection_info = router_manager.get_router_connection_info(router_name)
    if not connection_info:
        bot.reply_to(message, MESSAGES['error_router_not_found'])
        user_state_manager.clear_user_state(message.from_user.id)
        return
    
    # Виконуємо скрипт
    ssh_client = RouterSSHClient(
        connection_info['ip'], 
        connection_info['username'], 
        connection_info['ssh_password'], 
        connection_info['ssh_port']
    )
    result = ssh_client.execute_script(script)

    # Логування
    execution_time = get_current_time()
    log_message = LOG_MESSAGES['script_executed'].format(script, router_name, execution_time)
    logging.info(log_message)

    # Повідомлення адміністраторів через оптимізований клас
    admin_notifier.send_script_execution_notification(execution_time, message.from_user.username, router_name, script)

    # Відповідь користувачу
    bot.reply_to(message, MESSAGES['script_result'].format(script, result))
    
    # Очищаємо стан користувача після успішного виконання
    user_state_manager.clear_user_state(message.from_user.id)

def handle_wrong_password(message, script: str):
    """Обробляє невірний пароль"""
    bot.reply_to(message, MESSAGES['wrong_password'])
    logging.warning(LOG_MESSAGES['wrong_password_attempt'].format(message.from_user.username, script))

# Обробка підтвердження користувача (режим без пароля)
@bot.message_handler(func=lambda message: user_state_manager.is_in_state(message.from_user.id, USER_STATES['waiting_for_confirmation']))
def handle_confirmation_and_execute(message):
    router_name = user_state_manager.get_router_name(message.from_user.id)
    script = user_state_manager.get_script_name(message.from_user.id)
    
    if not router_name or not script:
        bot.reply_to(message, MESSAGES['error_router_not_found'])
        user_state_manager.clear_user_state(message.from_user.id)
        return
    
    # Перевіряємо відповідь користувача
    if is_positive_confirmation(message.text):
        execute_script_with_confirmation(message, router_name, script)
    elif is_negative_confirmation(message.text):
        handle_script_cancellation(message, router_name, script)
    else:
        bot.reply_to(message, MESSAGES['invalid_response'])
        return

def execute_script_with_confirmation(message, router_name: str, script: str):
    """Виконує скрипт в режимі підтвердження"""
    # Отримуємо інформацію для підключення з кешу
    connection_info = router_manager.get_router_connection_info(router_name)
    if not connection_info:
        bot.reply_to(message, MESSAGES['error_router_not_found'])
        user_state_manager.clear_user_state(message.from_user.id)
        return
    
    # Виконуємо скрипт без перевірки пароля
    ssh_client = RouterSSHClient(
        connection_info['ip'], 
        connection_info['username'], 
        connection_info['ssh_password'], 
        connection_info['ssh_port']
    )
    result = ssh_client.execute_script(script)

    # Логування
    execution_time = get_current_time()
    log_message = LOG_MESSAGES['script_executed_confirmation'].format(script, router_name, execution_time)
    logging.info(log_message)

    # Повідомлення адміністраторів через оптимізований клас
    admin_notifier.send_script_execution_notification(execution_time, message.from_user.username, router_name, script)

    # Відповідь користувачу
    bot.reply_to(message, MESSAGES['script_success'].format(script, result))
    
    # Очищаємо стан користувача
    user_state_manager.clear_user_state(message.from_user.id)

def handle_script_cancellation(message, router_name: str, script: str):
    """Обробляє скасування виконання скрипта"""
    bot.reply_to(message, MESSAGES['script_cancelled'])
    logging.info(LOG_MESSAGES['script_cancelled_by_user'].format(message.from_user.username, script, router_name))
    
    # Очищаємо стан користувача
    user_state_manager.clear_user_state(message.from_user.id)

# Обробка callback-запитів для управління доступом
@bot.callback_query_handler(func=lambda call: call.data.startswith('access_'))
def handle_access_management(call):
    if not access_manager.is_admin(call.from_user.id):
        # Логуємо спробу доступу до забороненої функції
        log_access_attempt(
            call.from_user.id, 
            call.from_user.username, 
            f"access_callback_{call.data}", 
            "BLOCKED", 
            "Спроба доступу до функцій управління доступом"
        )
        bot.answer_callback_query(call.id, "❌ У вас немає прав для управління доступом")
        return
    
    # Логуємо успішний доступ до функцій управління
    log_access_attempt(
        call.from_user.id, 
        call.from_user.username, 
        f"access_callback_{call.data}", 
        "SUCCESS", 
        "Доступ до функцій управління доступом"
    )
    
    action = call.data.split('_')[1]
    
    # Обробка кнопки "Назад до списку роутерів"
    if call.data == "access_main_menu" or (len(call.data.split('_')) >= 3 and call.data.split('_')[1] == 'main' and call.data.split('_')[2] == 'menu'):
        # Повертаємося до головного меню з переліком роутерів
        keyboard = access_manager.create_management_keyboard()
        
        # Отримуємо загальну статистику для заголовка
        routers_info = access_manager.get_all_routers_info()
        total_routers = len(routers_info)
        total_users = sum(info['users_count'] for info in routers_info.values())
        
        header_text = f"🔐 **Управління доступом користувачів**\n\n"
        header_text += f"📊 **Загальна статистика:**\n"
        header_text += f"🌐 Роутерів: {total_routers}\n"
        header_text += f"👥 Користувачів: {total_users}\n\n"
        header_text += f"📋 **Виберіть роутер для редагування користувачів:**"
        
        safe_edit_message_text(bot, header_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
    
    elif action == 'manage':
        # access_manage_{router_name} - показуємо меню управління роутером
        parts = call.data.split('_', 2)
        if len(parts) >= 3:
            router_name = parts[2]
            
            # Отримуємо детальну інформацію про роутер
            routers_info = access_manager.get_all_routers_info()
            if router_name in routers_info:
                info = routers_info[router_name]
                header_text = f"🔐 **Управління роутером {router_name}**\n\n"
                header_text += f"🌐 **IP:** `{info['ip']}`\n"
                header_text += f"👥 **Користувачів:** {info['users_count']}\n"
                header_text += f"🖥️ **Скрипти:** {', '.join(info['scripts'])}\n\n"
                header_text += f"📋 **Виберіть дію:**"
            else:
                header_text = f"🔐 **Управління роутером {router_name}**\n\n📋 **Виберіть дію:**"
            
            keyboard = access_manager.create_router_management_keyboard(router_name)
            safe_edit_message_text(bot, header_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'general_info':
        keyboard = access_manager.create_general_info_keyboard()
        safe_edit_message_text(bot, "📋 Загальна інформація про систему:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif action == 'list_all_users':
        routers_info = access_manager.get_all_routers_info()
        if routers_info:
            info_text = "📋 Список користувачів по роутерах:\n\n"
            for router_name, info in routers_info.items():
                users_list = ", ".join(info['allowed_users']) if info['allowed_users'] else "немає"
                info_text += f"**{router_name}**: {users_list}\n"
            
            safe_edit_message_text(bot, info_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        else:
            safe_edit_message_text(bot, "❌ Помилка отримання списку користувачів", call.message.chat.id, call.message.message_id)
    
    elif action == 'router_info':
        routers_info = access_manager.get_all_routers_info()
        if routers_info:
            info_text = MESSAGES['access_router_info'].format("")
            for router_name, info in routers_info.items():
                info_text += f"**{router_name}**\n"
                info_text += f"IP: {info['ip']}\n"
                info_text += f"Скрипти: {', '.join(info['scripts'])}\n"
                info_text += f"Користувачів: {info['users_count']}\n\n"
            
            safe_edit_message_text(bot, info_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        else:
            safe_edit_message_text(bot, "❌ Помилка отримання інформації про роутери", call.message.chat.id, call.message.message_id)
    
    elif action == 'all_routers_info':
        routers_info = access_manager.get_all_routers_info()
        if routers_info:
            info_text = "🌐 **Інформація про всі роутери:**\n\n"
            for router_name, info in routers_info.items():
                info_text += f"**{router_name}**\n"
                info_text += f"IP: `{info['ip']}`\n"
                info_text += f"Скрипти: {', '.join(info['scripts'])}\n"
                info_text += f"Користувачів: {info['users_count']}\n\n"
            
            safe_edit_message_text(bot, info_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        else:
            safe_edit_message_text(bot, "❌ Помилка отримання інформації про роутери", call.message.chat.id, call.message.message_id)
    
    elif action == 'stats':
        routers_info = access_manager.get_all_routers_info()
        if routers_info:
            total_routers = len(routers_info)
            total_users = sum(info['users_count'] for info in routers_info.values())
            total_scripts = sum(len(info['scripts']) for info in routers_info.values())
            
            stats_text = f"📊 **Статистика системи:**\n\n"
            stats_text += f"🌐 **Роутерів:** {total_routers}\n"
            stats_text += f"👥 **Користувачів:** {total_users}\n"
            stats_text += f"🖥️ **Скриптів:** {total_scripts}\n\n"
            
            # Детальна статистика по роутерах
            stats_text += "📋 **Деталі по роутерах:**\n"
            for router_name, info in routers_info.items():
                stats_text += f"• **{router_name}**: {info['users_count']} користувачів, {len(info['scripts'])} скриптів\n"
            
            keyboard = access_manager.create_management_keyboard()
            safe_edit_message_text(bot, stats_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
        else:
            safe_edit_message_text(bot, "❌ Помилка отримання статистики", call.message.chat.id, call.message.message_id)
    
    elif action == 'refresh':
        # Очищаємо кеш та отримуємо свіжі дані
        access_manager.router_manager.clear_cache()
        routers_info = access_manager.get_all_routers_info()
        
        if routers_info:
            total_routers = len(routers_info)
            total_users = sum(info['users_count'] for info in routers_info.values())
            
            header_text = f"🔄 **Кеш оновлено!**\n\n"
            header_text += f"📊 **Загальна статистика:**\n"
            header_text += f"🌐 Роутерів: {total_routers}\n"
            header_text += f"👥 Користувачів: {total_users}\n\n"
            header_text += f"📋 **Виберіть роутер для редагування користувачів:**"
            
            keyboard = access_manager.create_management_keyboard()
            safe_edit_message_text(bot, header_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ Помилка оновлення кешу")
    
    # Обробка дій з конкретним роутером
    elif action == 'view':
        # Формат: access_view_users_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            success, users = access_manager.get_router_users(router_name)
            
            if success and users:
                users_list = "\n".join([f"• {user_id}" for user_id in users])
                message_text = f"👥 **Користувачі роутера {router_name}**:\n\n{users_list}"
            else:
                message_text = f"👥 **У роутера {router_name} немає користувачів**"
            
            keyboard = access_manager.create_router_management_keyboard(router_name)
            safe_edit_message_text(bot, message_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'router_details':
        # Формат: access_router_details_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            routers_info = access_manager.get_all_routers_info()
            
            if router_name in routers_info:
                info = routers_info[router_name]
                message_text = f"📊 **Деталі роутера {router_name}**:\n\n"
                message_text += f"🌐 **IP:** `{info['ip']}`\n"
                message_text += f"🖥️ **Скрипти:** {', '.join(info['scripts'])}\n"
                message_text += f"👥 **Користувачів:** {info['users_count']}\n"
                message_text += f"📋 **Користувачі:** {', '.join(info['allowed_users']) if info['allowed_users'] else 'немає'}"
            else:
                message_text = f"❌ **Роутер {router_name} не знайдено**"
            
            keyboard = access_manager.create_router_management_keyboard(router_name)
            safe_edit_message_text(bot, message_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'refresh_router':
        # Формат: access_refresh_router_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            
            # Очищаємо кеш та отримуємо свіжі дані
            access_manager.router_manager.clear_cache()
            routers_info = access_manager.get_all_routers_info()
            
            if router_name in routers_info:
                info = routers_info[router_name]
                
                # Формуємо оновлений заголовок
                header_text = f"🔄 **Дані роутера {router_name} оновлено!**\n\n"
                header_text += f"🌐 **IP:** `{info['ip']}`\n"
                header_text += f"👥 **Користувачів:** {info['users_count']}\n"
                header_text += f"🖥️ **Скрипти:** {', '.join(info['scripts'])}\n\n"
                header_text += f"📋 **Виберіть дію:**"
                
                # Створюємо оновлену клавіатуру
                keyboard = access_manager.create_router_management_keyboard(router_name)
                
                safe_edit_message_text(bot, header_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')
            else:
                bot.answer_callback_query(call.id, f"❌ Роутер {router_name} не знайдено")
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    # Обробка додавання/видалення користувача для конкретного роутера
    elif action in ['add', 'remove']:
        # Формат: access_add_user_{router_name} або access_remove_user_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            operation = 'додавання' if action == 'add' else 'видалення'
            state_key = f'waiting_for_user_id_{action}'
            user_state_manager.set_state(call.from_user.id, state_key, router_name=router_name)
            
            bot.edit_message_text(
                f"📝 Введіть ID користувача для {operation} до роутера {router_name}:",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    # Обробка кнопок з користувачами (нові обробники)
    elif action == 'view_users':
        # Формат: access_view_users_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            success, users = access_manager.get_router_users(router_name)
            
            if success and users:
                users_list = "\n".join([f"• {user_id}" for user_id in users])
                message_text = f"👥 Користувачі роутера {router_name}:\n\n{users_list}"
            else:
                message_text = f"👥 У роутера {router_name} немає користувачів"
            
            keyboard = access_manager.create_router_management_keyboard(router_name)
            safe_edit_message_text(bot, message_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'add_user':
        # Формат: access_add_user_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            user_state_manager.set_state(call.from_user.id, 'waiting_for_user_id_add', router_name=router_name)
            
            bot.edit_message_text(
                f"📝 Введіть ID користувача для додавання до роутера {router_name}:",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'remove_user':
        # Формат: access_remove_user_{router_name}
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            user_state_manager.set_state(call.from_user.id, 'waiting_for_user_id_remove', router_name=router_name)
            
            bot.edit_message_text(
                f"📝 Введіть ID користувача для видалення з роутера {router_name}:",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    # Додаткові обробники для різних форматів callback
    elif action == 'add':
        # Формат: access_add_user_{router_name} (якщо розбито по-іншому)
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            user_state_manager.set_state(call.from_user.id, 'waiting_for_user_id_add', router_name=router_name)
            
            bot.edit_message_text(
                f"📝 Введіть ID користувача для додавання до роутера {router_name}:",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")
    
    elif action == 'remove':
        # Формат: access_remove_user_{router_name} (якщо розбито по-іншому)
        parts = call.data.split('_', 3)
        if len(parts) >= 4:
            router_name = parts[3]
            user_state_manager.set_state(call.from_user.id, 'waiting_for_user_id_remove', router_name=router_name)
            
            bot.edit_message_text(
                f"📝 Введіть ID користувача для видалення з роутера {router_name}:",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка: не вдалося отримати назву роутера")

# Обробка введення ID користувача для додавання/видалення
@bot.message_handler(func=lambda message: user_state_manager.get_state(message.from_user.id) and 
                    user_state_manager.get_state(message.from_user.id).startswith('waiting_for_user_id_'))
def handle_user_id_input(message):
    state = user_state_manager.get_state(message.from_user.id)
    
    # Виправляємо логіку визначення дії
    if state == 'waiting_for_user_id_add':
        action = 'add'
    elif state == 'waiting_for_user_id_remove':
        action = 'remove'
    else:
        action = 'unknown'
    
    router_name = user_state_manager.get_user_data(message.from_user.id, 'router_name')
    user_id = message.text.strip()
    
    if not router_name:
        bot.reply_to(message, "❌ Помилка: не вдалося отримати назву роутера")
        user_state_manager.clear_user_state(message.from_user.id)
        return
    
    if not access_manager.validate_user_id(user_id):
        bot.reply_to(message, MESSAGES['access_invalid_user_id'])
        return
    
    if action == 'add':
        success, message_text = access_manager.add_user_access(router_name, user_id)
        # Логуємо спробу додавання користувача
        log_access_attempt(
            message.from_user.id, 
            message.from_user.username, 
            f"add_user_{router_name}", 
            "SUCCESS" if success else "FAILED", 
            f"Спроба додати користувача {user_id} до роутера {router_name}"
        )
    elif action == 'remove':
        success, message_text = access_manager.remove_user_access(router_name, user_id)
        # Логуємо спробу видалення користувача
        log_access_attempt(
            message.from_user.id, 
            message.from_user.username, 
            f"remove_user_{router_name}", 
            "SUCCESS" if success else "FAILED", 
            f"Спроба видалити користувача {user_id} з роутера {router_name}"
        )
    else:
        bot.reply_to(message, "❌ Помилка: невідома дія")
        user_state_manager.clear_user_state(message.from_user.id)
        return
    
    if success:
        # Створюємо клавіатуру для повернення до управління роутером
        keyboard = access_manager.create_router_management_keyboard(router_name)
        bot.reply_to(message, f"{message_text}\n\n🔙 Повертаюся до меню управління роутером {router_name}", 
                    reply_markup=keyboard)
    else:
        bot.reply_to(message, message_text)
    
    # Очищаємо стан користувача
    user_state_manager.clear_user_state(message.from_user.id)

def safe_edit_message_text(bot, text, chat_id, message_id, reply_markup=None, parse_mode=None):
    """Безпечно редагує повідомлення з обробкою помилки 'message is not modified'"""
    try:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        if "message is not modified" in str(e):
            # Повідомлення не змінилося - це не помилка
            pass
        else:
            # Інша помилка - логуємо
            logging.error(f"Помилка редагування повідомлення: {e}")
            # Спробуємо відправити нове повідомлення
            try:
                bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as send_error:
                logging.error(f"Помилка відправки нового повідомлення: {send_error}")

# Запуск бота
if __name__ == "__main__":
    logging.info(LOG_MESSAGES['bot_started'])
    
    # Логуємо статус налаштувань
    notification_status = admin_notifier.get_notification_status()
    for admin_num, status in notification_status.items():
        if 'enabled' in admin_num:
            admin_id = admin_num.split('_')[1]
            enabled = 'включені' if status else 'відключені'
            logging.info(LOG_MESSAGES['notifications_status'].format(admin_id, enabled))
    
    logging.info(LOG_MESSAGES['script_mode_status'].format(
        'з паролем' if SCRIPT_PASSWORD_MODE else 'з підтвердженням'
    ))
    
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logging.info("Бот зупинено користувачем")
        admin_notifier.cleanup()
    except Exception as e:
        logging.error(f"Помилка в роботі бота: {e}")
        admin_notifier.cleanup()
