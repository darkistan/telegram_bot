import json
import logging
from typing import Dict, List, Tuple, Any, Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from router_manager import RouterManager

class AccessManager:
    """Клас для управління доступом користувачів до роутерів"""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.router_manager = RouterManager(config_file)
    
    def is_admin(self, user_id: int) -> bool:
        """Перевіряє, чи є користувач адміністратором"""
        # Отримуємо список адміністраторів через router_manager
        admin_ids = self._get_admin_ids()
        return str(user_id) in admin_ids
    
    def _get_admin_ids(self) -> List[str]:
        """Отримує список ID адміністраторів через кеш"""
        try:
            routers = self.router_manager.get_routers()
            return routers.get('admins', ['440127888'])  # За замовчуванням
        except Exception as e:
            logging.error(f"Помилка отримання списку адміністраторів: {e}")
            return ['440127888']
    
    def add_user_access(self, router_name: str, user_id: str) -> Tuple[bool, str]:
        """Додає користувача до списку дозволених для роутера"""
        try:
            # Отримуємо поточні дані через router_manager
            routers = self.router_manager.get_routers()
            
            if router_name not in routers:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'allowed_users' not in routers[router_name]:
                routers[router_name]['allowed_users'] = []
            
            if user_id in routers[router_name]['allowed_users']:
                return False, f"Користувач {user_id} вже має доступ до роутера '{router_name}'"
            
            # Додаємо користувача
            routers[router_name]['allowed_users'].append(user_id)
            
            # Зберігаємо зміни в файл
            self._save_routers_to_file(routers)
            
            # Очищаємо кеш для оновлення даних
            self.router_manager.clear_cache()
            
            logging.info(f"Користувач {user_id} додано до роутера {router_name}")
            return True, f"Користувач {user_id} успішно додано до роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка додавання користувача {user_id} до роутера {router_name}: {e}")
            return False, f"Помилка додавання користувача: {e}"
    
    def remove_user_access(self, router_name: str, user_id: str) -> Tuple[bool, str]:
        """Видаляє користувача зі списку дозволених для роутера"""
        try:
            # Отримуємо поточні дані через router_manager
            routers = self.router_manager.get_routers()
            
            if router_name not in routers:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'allowed_users' not in routers[router_name]:
                return False, f"У роутера '{router_name}' немає списку дозволених користувачів"
            
            if user_id not in routers[router_name]['allowed_users']:
                return False, f"Користувач {user_id} не має доступу до роутера '{router_name}'"
            
            # Видаляємо користувача
            routers[router_name]['allowed_users'].remove(user_id)
            
            # Зберігаємо зміни в файл
            self._save_routers_to_file(routers)
            
            # Очищаємо кеш для оновлення даних
            self.router_manager.clear_cache()
            
            logging.info(f"Користувач {user_id} видалено з роутера {router_name}")
            return True, f"Користувач {user_id} успішно видалено з роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка видалення користувача {user_id} з роутера {router_name}: {e}")
            return False, f"Помилка видалення користувача: {e}"
    
    def get_router_users(self, router_name: str) -> Tuple[bool, List[str]]:
        """Отримує список користувачів для конкретного роутера через кеш"""
        try:
            router = self.router_manager.get_router(router_name)
            if not router:
                return False, []
            
            return True, router.get('allowed_users', [])
            
        except Exception as e:
            logging.error(f"Помилка отримання користувачів роутера {router_name}: {e}")
            return False, []
    
    def get_all_routers_info(self) -> Dict[str, Dict]:
        """Отримує інформацію про всі роутери та їх користувачів через кеш"""
        try:
            routers = self.router_manager.get_routers()
            
            routers_info = {}
            for router_name, router_data in routers.items():
                # Пропускаємо секцію адміністраторів та інші не-роутери
                if router_name == 'admins' or not isinstance(router_data, dict):
                    continue
                
                routers_info[router_name] = {
                    'ip': router_data.get('ip', 'N/A'),
                    'scripts': router_data.get('scripts', []),
                    'users_count': len(router_data.get('allowed_users', [])),
                    'allowed_users': router_data.get('allowed_users', [])
                }
            
            return routers_info
            
        except Exception as e:
            logging.error(f"Помилка отримання інформації про роутери: {e}")
            return {}
    
    def create_management_keyboard(self) -> InlineKeyboardMarkup:
        """Створює клавіатуру для управління доступом - одразу показує роутери"""
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        # Отримуємо список роутерів через кеш
        routers = self.router_manager.get_routers()
        
        for router_name, router_data in routers.items():
            # Пропускаємо секцію адміністраторів та інші не-роутери
            if router_name == 'admins' or not isinstance(router_data, dict):
                continue
            
            # Отримуємо додаткову інформацію про роутер
            ip = router_data.get('ip', 'N/A')
            users_count = len(router_data.get('allowed_users', []))
            
            # Створюємо текст кнопки з інформацією
            button_text = f"🌐 {router_name}\n📡 {ip} | 👥 {users_count}"
            
            keyboard.add(
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"access_router_details_{router_name}"
                )
            )
        
        # Додаємо кнопки управління
        keyboard.add(
            InlineKeyboardButton("📊 Статистика", callback_data="access_stats")
        )
        keyboard.add(
            InlineKeyboardButton("🔄 Оновити кеш", callback_data="access_refresh_cache")
        )
        
        return keyboard
    
    def create_router_management_keyboard(self, router_name: str) -> InlineKeyboardMarkup:
        """Створює клавіатуру для управління конкретним роутером"""
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        # Отримуємо дані роутера через кеш
        router = self.router_manager.get_router(router_name)
        if not router:
            return keyboard
        
        # Отримуємо кількість користувачів та скриптів
        users_count = len(router.get('allowed_users', []))
        scripts_count = len(router.get('scripts', []))
        
        # Кнопки управління користувачами
        keyboard.add(
            InlineKeyboardButton(f"👥 Активні користувачі ({users_count})", callback_data=f"access_view_users_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➕ Додати користувача", callback_data=f"access_add_user_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➖ Видалити користувача", callback_data=f"access_remove_user_{router_name}")
        )
        
        # Розділювач
        keyboard.add(
            InlineKeyboardButton("─" * 20, callback_data="access_separator")
        )
        
        # Кнопки управління скриптами
        keyboard.add(
            InlineKeyboardButton(f"📜 Скрипти ({scripts_count})", callback_data=f"access_viewscripts_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➕ Додати скрипт", callback_data=f"access_addscript_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➖ Видалити скрипт", callback_data=f"access_removescript_{router_name}")
        )
        
        # Кнопка оновлення кешу для конкретного роутера
        keyboard.add(
            InlineKeyboardButton("🔄 Оновити кеш роутера", callback_data=f"access_refresh_router_{router_name}")
        )
        
        # Кнопка повернення
        keyboard.add(
            InlineKeyboardButton("⬅️ Назад до списку", callback_data="access_back_to_list")
        )
        
        return keyboard
    
    def add_script_to_router(self, router_name: str, script_name: str) -> Tuple[bool, str]:
        """Додає скрипт до роутера"""
        try:
            # Отримуємо поточні дані через router_manager
            routers = self.router_manager.get_routers()
            
            if router_name not in routers:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'scripts' not in routers[router_name]:
                routers[router_name]['scripts'] = []
            
            if script_name in routers[router_name]['scripts']:
                return False, f"Скрипт '{script_name}' вже існує в роутері '{router_name}'"
            
            # Додаємо скрипт
            routers[router_name]['scripts'].append(script_name)
            
            # Зберігаємо зміни в файл
            self._save_routers_to_file(routers)
            
            # Очищаємо кеш для оновлення даних
            self.router_manager.clear_cache()
            
            logging.info(f"Скрипт '{script_name}' додано до роутера {router_name}")
            return True, f"Скрипт '{script_name}' успішно додано до роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка додавання скрипта '{script_name}' до роутера {router_name}: {e}")
            return False, f"Помилка додавання скрипта: {e}"
    
    def remove_script_from_router(self, router_name: str, script_name: str) -> Tuple[bool, str]:
        """Видаляє скрипт з роутера"""
        try:
            # Отримуємо поточні дані через router_manager
            routers = self.router_manager.get_routers()
            
            if router_name not in routers:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'scripts' not in routers[router_name]:
                return False, f"У роутера '{router_name}' немає списку скриптів"
            
            if script_name not in routers[router_name]['scripts']:
                return False, f"Скрипт '{script_name}' не знайдено в роутері '{router_name}'"
            
            # Видаляємо скрипт
            routers[router_name]['scripts'].remove(script_name)
            
            # Зберігаємо зміни в файл
            self._save_routers_to_file(routers)
            
            # Очищаємо кеш для оновлення даних
            self.router_manager.clear_cache()
            
            logging.info(f"Скрипт '{script_name}' видалено з роутера {router_name}")
            return True, f"Скрипт '{script_name}' успішно видалено з роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка видалення скрипта '{script_name}' з роутера {router_name}: {e}")
            return False, f"Помилка видалення скрипта: {e}"
    
    def get_router_scripts(self, router_name: str) -> Tuple[bool, List[str]]:
        """Отримує список скриптів для конкретного роутера через кеш"""
        try:
            router = self.router_manager.get_router(router_name)
            if not router:
                return False, []
            
            scripts = router.get('scripts', [])
            return True, scripts
            
        except Exception as e:
            logging.error(f"Помилка отримання скриптів роутера {router_name}: {e}")
            return False, []
    
    def validate_script_name(self, script_name: str) -> bool:
        """Валідує назву скрипта"""
        if not script_name or not script_name.strip():
            return False
        
        # Перевіряємо, чи не містить заборонені символи
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        return not any(char in script_name for char in forbidden_chars)
    
    def validate_user_id(self, user_id: str) -> bool:
        """Валідує ID користувача"""
        try:
            # Перевіряємо, чи є це число
            int(user_id)
            # Перевіряємо довжину (Telegram ID зазвичай 7-10 цифр)
            return 7 <= len(user_id) <= 10
        except ValueError:
            return False
    
    def clear_cache(self):
        """Очищає кеш router_manager"""
        self.router_manager.clear_cache()
    
    def _save_routers_to_file(self, routers: Dict[str, Any]):
        """Зберігає дані роутерів у файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as file:
                json.dump(routers, file, indent=2, ensure_ascii=False)
            logging.info(f"Дані роутерів збережено у файл {self.config_file}")
        except Exception as e:
            logging.error(f"Помилка збереження даних роутерів: {e}")
            raise 