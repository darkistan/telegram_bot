import telebot
import logging
from typing import Optional
from config import (
    ADMIN_1_ID, ADMIN_2_ID, ADMIN_BOT_1_TOKEN, ADMIN_BOT_2_TOKEN,
    ADMIN_1_NOTIFICATIONS_ENABLED, ADMIN_2_NOTIFICATIONS_ENABLED
)
from constants import format_admin_message, LOG_MESSAGES

class AdminNotifier:
    """Клас для оптимізованого створення ботів та повідомлень адміністраторів"""
    
    def __init__(self):
        self._admin_bot_1: Optional[telebot.TeleBot] = None
        self._admin_bot_2: Optional[telebot.TeleBot] = None
        self._bots_initialized = False
    
    def _initialize_bots(self):
        """Ініціалізує боти для адміністраторів (тільки один раз)"""
        if self._bots_initialized:
            return
        
        if ADMIN_1_NOTIFICATIONS_ENABLED:
            try:
                self._admin_bot_1 = telebot.TeleBot(ADMIN_BOT_1_TOKEN)
                logging.info("Бот для ADMIN_1 успішно ініціалізовано")
            except Exception as e:
                logging.error(f"Помилка ініціалізації бота для ADMIN_1: {e}")
                self._admin_bot_1 = None
        
        if ADMIN_2_NOTIFICATIONS_ENABLED:
            try:
                self._admin_bot_2 = telebot.TeleBot(ADMIN_BOT_2_TOKEN)
                logging.info("Бот для ADMIN_2 успішно ініціалізовано")
            except Exception as e:
                logging.error(f"Помилка ініціалізації бота для ADMIN_2: {e}")
                self._admin_bot_2 = None
        
        self._bots_initialized = True
    
    def send_access_request_notification(self, user_info: dict):
        """Відправляє повідомлення про запит доступу"""
        self._initialize_bots()
        
        admin_message = (
            f"Користувач {user_info['first_name']} {user_info['last_name']} "
            f"({user_info['username']}) з ID {user_info['id']} запросив доступ.\n"
            f"Будь ласка, відредагуйте файл routers.json для надання доступу."
        )
        
        self._send_to_all_admins(admin_message)
    
    def send_script_execution_notification(self, execution_time: str, username: str, 
                                         router_name: str, script: str):
        """Відправляє повідомлення про виконання скрипта"""
        self._initialize_bots()
        
        admin_message = format_admin_message(execution_time, username, router_name, script)
        self._send_to_all_admins(admin_message)
    
    def _send_to_all_admins(self, message: str):
        """Відправляє повідомлення всім активним адміністраторам"""
        sent_count = 0
        
        if ADMIN_1_NOTIFICATIONS_ENABLED and self._admin_bot_1:
            try:
                self._admin_bot_1.send_message(ADMIN_1_ID, message)
                sent_count += 1
            except Exception as e:
                logging.error(f"Помилка відправки повідомлення ADMIN_1: {e}")
        
        if ADMIN_2_NOTIFICATIONS_ENABLED and self._admin_bot_2:
            try:
                self._admin_bot_2.send_message(ADMIN_2_ID, message)
                sent_count += 1
            except Exception as e:
                logging.error(f"Помилка відправки повідомлення ADMIN_2: {e}")
        
        if sent_count > 0:
            logging.info(f"Повідомлення успішно відправлено {sent_count} адміністраторам")
        else:
            logging.warning("Не вдалося відправити повідомлення жодному адміністратору")
    
    def get_notification_status(self) -> dict:
        """Отримує статус налаштувань повідомлень"""
        return {
            'admin_1_enabled': ADMIN_1_NOTIFICATIONS_ENABLED,
            'admin_2_enabled': ADMIN_2_NOTIFICATIONS_ENABLED,
            'admin_1_bot_ready': self._admin_bot_1 is not None,
            'admin_2_bot_ready': self._admin_bot_2 is not None
        }
    
    def test_connections(self) -> dict:
        """Тестує з'єднання з адміністраторами"""
        self._initialize_bots()
        
        test_message = "🧪 Тестове повідомлення для перевірки з'єднання"
        results = {}
        
        if ADMIN_1_NOTIFICATIONS_ENABLED and self._admin_bot_1:
            try:
                self._admin_bot_1.send_message(ADMIN_1_ID, test_message)
                results['admin_1'] = 'success'
            except Exception as e:
                results['admin_1'] = f'error: {e}'
        else:
            results['admin_1'] = 'disabled'
        
        if ADMIN_2_NOTIFICATIONS_ENABLED and self._admin_bot_2:
            try:
                self._admin_bot_2.send_message(ADMIN_2_ID, test_message)
                results['admin_2'] = 'success'
            except Exception as e:
                results['admin_2'] = f'error: {e}'
        else:
            results['admin_2'] = 'disabled'
        
        return results
    
    def cleanup(self):
        """Очищає ресурси ботів"""
        if self._admin_bot_1:
            try:
                self._admin_bot_1.stop_polling()
            except:
                pass
            self._admin_bot_1 = None
        
        if self._admin_bot_2:
            try:
                self._admin_bot_2.stop_polling()
            except:
                pass
            self._admin_bot_2 = None
        
        self._bots_initialized = False
        logging.info("Ресурси адміністративних ботів очищено") 