import logging
import json
import telebot
from datetime import datetime
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import (
    BOT_TOKEN, ADMIN_1_ID, ADMIN_2_ID, ADMIN_BOT_1_TOKEN, ADMIN_BOT_2_TOKEN,
    ADMIN_1_NOTIFICATIONS_ENABLED, ADMIN_2_NOTIFICATIONS_ENABLED
)
from fabric import Connection
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError

# Настроим логирование с ротацией
from logging.handlers import RotatingFileHandler

# Устанавливаем параметры логирования
log_handler = RotatingFileHandler('logs/bot.log', maxBytes=10 * 1024 * 1024, backupCount=5)
log_handler.setLevel(logging.INFO)  # Устанавливаем уровень логирования
formatter = logging.Formatter('%(asctime)s - %(message)s')
log_handler.setFormatter(formatter)

# Добавляем обработчик в корневой логгер
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

# Инициализация бота для пользователей
bot = telebot.TeleBot(BOT_TOKEN)

# Класс для работы с SSH через Fabric
class RouterSSHClient:
    def __init__(self, ip: str, username: str, ssh_password: str, ssh_port: int = 22):
        """
        Инициализация клиента SSH.
        
        :param ip: IP-адрес маршрутизатора
        :param username: Имя пользователя для подключения по SSH
        :param ssh_password: Пароль для подключения по SSH
        :param ssh_port: Порт для подключения по SSH (по умолчанию 22)
        """
        self.ip = ip
        self.username = username
        self.ssh_password = ssh_password
        self.ssh_port = ssh_port  # Учитываем порт для SSH

    def execute_script(self, script: str) -> str:
        """
        Выполнение скрипта на роутере через SSH.
        
        :param script: Название скрипта, который нужно выполнить
        :return: Результат выполнения скрипта
        """
        try:
            # Создаем подключение через Fabric
            conn = Connection(
                host=self.ip, 
                user=self.username, 
                connect_kwargs={"password": self.ssh_password},  # Используем ssh_password для SSH-подключения
                port=self.ssh_port  # Указываем порт для подключения
            )
            # Выполнение скрипта на маршрутизаторе
            result = conn.run(f"/system script run {script}", hide=True)
            return result.stdout
        except AuthenticationException as e:
            logging.error(f"Ошибка аутентификации: {e}")
            return "Ошибка аутентификации. Проверьте правильность пароля SSH."
        except NoValidConnectionsError as e:
            logging.error(f"Ошибка соединения: {e}")
            return f"Ошибка соединения. Проверьте доступность маршрутизатора по IP-адресу {self.ip} и порту {self.ssh_port}."
        except SSHException as e:
            logging.error(f"Ошибка SSH: {e}")
            return f"Ошибка SSH: {e}"
        except Exception as e:
            logging.error(f"Неизвестная ошибка при выполнении скрипта: {e}")
            return f"Неизвестная ошибка при выполнении скрипта: {e}"

# Состояние для хранения данных пользователя
user_state = {}

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 'Привет! Я бот для управления маршрутизаторами.')
    logging.info(f"Пользователь {message.from_user.username} начал взаимодействие с ботом.")

# Обработчик команды /id для запроса доступа
@bot.message_handler(commands=['id'])
def request_access(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    user_first_name = message.from_user.first_name
    user_last_name = message.from_user.last_name

    # Отправляем уведомление администраторам
    admin_message = f"Пользователь {user_first_name} {user_last_name} ({user_name}) с ID {user_id} запросил доступ.\n" \
                    f"Пожалуйста, отредактируйте файл routers.json для предоставления доступа."

    # Отправка сообщения администраторам с проверкой настроек
    if ADMIN_1_NOTIFICATIONS_ENABLED:
        admin_bot_1 = telebot.TeleBot(ADMIN_BOT_1_TOKEN)
        admin_bot_1.send_message(ADMIN_1_ID, admin_message)
    
    if ADMIN_2_NOTIFICATIONS_ENABLED:
        admin_bot_2 = telebot.TeleBot(ADMIN_BOT_2_TOKEN)
        admin_bot_2.send_message(ADMIN_2_ID, admin_message)

    # Подтверждаем запрос пользователю
    bot.reply_to(message, "Ваш запрос на доступ отправлен администраторам. Ожидайте их решение.")

# Отправка выбора маршрутизаторов
@bot.message_handler(commands=['run_script'])
def send_router_selection(message):
    logging.info(f"Пользователь {message.from_user.username} выбрал команду /run_script.")
    
    try:
        with open('routers.json', 'r') as file:
            routers = json.load(file)

        logging.info(f"Загруженные роутеры: {routers}")  # Логируем все роутеры
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла routers.json: {e}")
        bot.reply_to(message, "Ошибка при загрузке данных о маршрутизаторах.")
        return

    # Создаем InlineKeyboardMarkup для роутеров
    keyboard = InlineKeyboardMarkup(row_width=1)
    for router in routers.keys():
        # Проверяем, имеет ли пользователь доступ к роутеру
        if str(message.from_user.id) in routers[router].get('allowed_users', []):
            # Создаем кнопки с правильным callback_data, теперь используем router_name в callback_data
            keyboard.add(InlineKeyboardButton(router, callback_data=f"router_{router}"))
    
    # Отправляем сообщение с кнопками выбора маршрутизаторов
    if keyboard.keyboard:
        bot.reply_to(message, "Выберите маршрутизатор:", reply_markup=keyboard)
        user_state[message.chat.id] = {'state': 'waiting_for_router'}  # Сохраняем состояние пользователя
    else:
        bot.reply_to(message, "У вас нет доступа к роутерам.")
        logging.info(f"Пользователь {message.from_user.username} не имеет доступа к роутерам.")

# Обработка выбора маршрутизатора
@bot.callback_query_handler(func=lambda call: call.data.startswith('router_'))
def handle_router_selection(call):
    router_name = call.data.split('_')[1]  # Берем имя маршрутизатора после 'router_'
    
    # Логируем выбор маршрутизатора
    logging.info(f"Пользователь выбрал маршрутизатор: {router_name}")

    try:
        with open('routers.json', 'r') as file:
            routers = json.load(file)
            logging.info(f"Загруженные роутеры: {routers}")  # Логируем все роутеры

        router = routers.get(router_name)
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла routers.json: {e}")
        bot.send_message(call.message.chat.id, "Ошибка при загрузке данных о маршрутизаторах.")
        return

    if router and str(call.from_user.id) in router.get('allowed_users', []):
        # Логируем выбор маршрутизатора
        logging.info(f"Пользователь {call.from_user.username} выбрал маршрутизатор: {router_name}")

        # Сохраняем выбранный маршрутизатор
        user_state[call.from_user.id] = {'router': router_name}

        # Создаем InlineKeyboardMarkup для скриптов
        keyboard = InlineKeyboardMarkup(row_width=1)
        for script in router["scripts"]:
            keyboard.add(InlineKeyboardButton(script, callback_data=f"script_{router_name}_{script}"))

        # Отправляем сообщение с кнопками выбора скрипта
        bot.send_message(call.message.chat.id, f"Выберите скрипт для {router_name}:", reply_markup=keyboard)
        user_state[call.from_user.id]['state'] = 'waiting_for_script'  # Переводим пользователя в состояние выбора скрипта
    else:
        bot.send_message(call.message.chat.id, "Ошибка: маршрутизатор не найден или у вас нет доступа.")
        logging.error(f"Маршрутизатор {router_name} не найден или пользователь {call.from_user.username} не имеет доступа.")

# Обработка выбора скрипта
@bot.callback_query_handler(func=lambda call: call.data.startswith('script_'))
def handle_script_selection(call):
    router_name, script = call.data.split('_')[1], call.data.split('_')[2]

    # Запрос пароля для выполнения скрипта
    bot.send_message(call.message.chat.id, f"Введите пароль для выполнения скрипта '{script}' на маршрутизаторе {router_name}:")
    user_state[call.from_user.id]['script'] = script  # Сохраняем выбранный скрипт
    user_state[call.from_user.id]['state'] = 'waiting_for_password'  # Переводим пользователя в состояние ввода пароля

# Проверка пароля и выполнение скрипта
@bot.message_handler(func=lambda message: message.chat.id in user_state and user_state[message.chat.id]['state'] == 'waiting_for_password')
def verify_password_and_execute(message):
    router_name = user_state[message.chat.id].get('router')
    script = user_state[message.chat.id].get('script')

    try:
        with open('routers.json', 'r') as file:
            routers = json.load(file)

        router = routers.get(router_name)
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла routers.json: {e}")
        bot.reply_to(message, "Ошибка при загрузке данных о маршрутизаторах.")
        return

    if router:
        # Проверка пароля для выполнения скрипта
        if message.text == router["script_password"]:  # Используем script_password для проверки
            ssh_client = RouterSSHClient(router["ip"], router["username"], router["ssh_password"], router["ssh_port"])  # Используем ssh_password и ssh_port для подключения
            result = ssh_client.execute_script(script)

            # Логирование
            execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_message = f"Скрипт '{script}' был выполнен на маршрутизаторе '{router_name}' в {execution_time}."
            logging.info(log_message)

            # Уведомление администраторов
            notify_admins(execution_time, message.from_user.username, router_name, script)

            # Ответ пользователю
            bot.reply_to(message, f"Результат выполнения скрипта '{script}':\n{result}")
        else:
            bot.reply_to(message, "Неверный пароль для выполнения скрипта. Попробуйте снова.")
            logging.warning(f"Пользователь {message.from_user.username} ввел неверный пароль для скрипта {script}.")
    else:
        bot.reply_to(message, "Ошибка: маршрутизатор не найден.")

# Уведомление администраторов
def notify_admins(execution_time: str, username: str, router_name: str, script: str):
    admin_message = f"🔔 Статус выполнения скрипта:\n\n" \
                    f"📅 Время: {execution_time}\n" \
                    f"👤 Кто запустил: {username}\n" \
                    f"🌐 Маршрутизатор: {router_name}\n" \
                    f"🖥 Скрипт: {script}"

    # Отправляем уведомление через боты с проверкой настроек
    if ADMIN_1_NOTIFICATIONS_ENABLED:
        admin_bot_1 = telebot.TeleBot(ADMIN_BOT_1_TOKEN)
        admin_bot_1.send_message(ADMIN_1_ID, admin_message)
    
    if ADMIN_2_NOTIFICATIONS_ENABLED:
        admin_bot_2 = telebot.TeleBot(ADMIN_BOT_2_TOKEN)
        admin_bot_2.send_message(ADMIN_2_ID, admin_message)

# Запуск бота
if __name__ == "__main__":
    logging.info("Бот запущен.")
    logging.info(f"Уведомления для ADMIN_1: {'включены' if ADMIN_1_NOTIFICATIONS_ENABLED else 'отключены'}")
    logging.info(f"Уведомления для ADMIN_2: {'включены' if ADMIN_2_NOTIFICATIONS_ENABLED else 'отключены'}")
    bot.polling(none_stop=True)
