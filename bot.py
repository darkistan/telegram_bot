import logging
import telebot
from datetime import datetime
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, SCRIPT_PASSWORD_MODE
from fabric import Connection
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError

# Імпорт нових модулів
from constants import MESSAGES, USER_STATES, LOG_MESSAGES, get_user_info, get_current_time, is_positive_confirmation, is_negative_confirmation
from router_manager import RouterManager
from user_state_manager import UserStateManager
from admin_notifier import AdminNotifier
from keyboard_utils import create_router_keyboard, create_script_keyboard

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

# Ініціалізація бота для користувачів
bot = telebot.TeleBot(BOT_TOKEN)

# Ініціалізація менеджерів
router_manager = RouterManager()
user_state_manager = UserStateManager()
admin_notifier = AdminNotifier()

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

# Відправка вибору маршрутизаторів
@bot.message_handler(commands=['run_script'])
def send_router_selection(message):
    logging.info(LOG_MESSAGES['user_selected_command'].format(message.from_user.username))
    
    # Отримуємо роутери користувача з кешу
    user_routers = router_manager.get_user_routers(message.from_user.id)
    
    if not user_routers:
        bot.reply_to(message, MESSAGES['no_access'])
        logging.info(LOG_MESSAGES['user_no_access'].format(message.from_user.username))
        return
    
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
        bot.send_message(call.message.chat.id, MESSAGES['router_not_found'])
        logging.error(f"Маршрутизатор {router_name} не знайдено або користувач {call.from_user.username} не має доступу.")
        return

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
