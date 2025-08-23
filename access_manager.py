import json
import logging
from typing import Dict, List, Optional, Tuple
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from router_manager import RouterManager

class AccessManager:
    """Клас для управління доступом користувачів до роутерів"""
    
    def __init__(self, config_file: str = 'routers.json'):
        self.config_file = config_file
        self.router_manager = RouterManager(config_file)
    
    def is_admin(self, user_id: int) -> bool:
        """Перевіряє, чи є користувач адміністратором"""
        # Отримуємо список адміністраторів з конфігурації
        admin_ids = self._get_admin_ids()
        return str(user_id) in admin_ids
    
    def _get_admin_ids(self) -> List[str]:
        """Отримує список ID адміністраторів"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
                return config.get('admins', ['440127888'])  # За замовчуванням
        except Exception as e:
            logging.error(f"Помилка отримання списку адміністраторів: {e}")
            return ['440127888']
    
    def add_user_access(self, router_name: str, user_id: str) -> Tuple[bool, str]:
        """Додає користувача до списку дозволених для роутера"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            if router_name not in config:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'allowed_users' not in config[router_name]:
                config[router_name]['allowed_users'] = []
            
            if user_id in config[router_name]['allowed_users']:
                return False, f"Користувач {user_id} вже має доступ до роутера '{router_name}'"
            
            config[router_name]['allowed_users'].append(user_id)
            
            # Зберігаємо зміни
            with open(self.config_file, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            
            # Очищаємо кеш роутерів
            self.router_manager.clear_cache()
            
            logging.info(f"Користувач {user_id} додано до роутера {router_name}")
            return True, f"Користувач {user_id} успішно додано до роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка додавання користувача {user_id} до роутера {router_name}: {e}")
            return False, f"Помилка додавання користувача: {e}"
    
    def remove_user_access(self, router_name: str, user_id: str) -> Tuple[bool, str]:
        """Видаляє користувача зі списку дозволених для роутера"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            if router_name not in config:
                return False, f"Роутер '{router_name}' не знайдено"
            
            if 'allowed_users' not in config[router_name]:
                return False, f"У роутера '{router_name}' немає списку дозволених користувачів"
            
            if user_id not in config[router_name]['allowed_users']:
                return False, f"Користувач {user_id} не має доступу до роутера '{router_name}'"
            
            config[router_name]['allowed_users'].remove(user_id)
            
            # Зберігаємо зміни
            with open(self.config_file, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            
            # Очищаємо кеш роутерів
            self.router_manager.clear_cache()
            
            logging.info(f"Користувач {user_id} видалено з роутера {router_name}")
            return True, f"Користувач {user_id} успішно видалено з роутера '{router_name}'"
            
        except Exception as e:
            logging.error(f"Помилка видалення користувача {user_id} з роутера {router_name}: {e}")
            return False, f"Помилка видалення користувача: {e}"
    
    def get_router_users(self, router_name: str) -> Tuple[bool, List[str]]:
        """Отримує список користувачів для конкретного роутера"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            if router_name not in config:
                return False, []
            
            return True, config[router_name].get('allowed_users', [])
            
        except Exception as e:
            logging.error(f"Помилка отримання користувачів роутера {router_name}: {e}")
            return False, []
    
    def get_all_routers_info(self) -> Dict[str, Dict]:
        """Отримує інформацію про всі роутери та їх користувачів"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            routers_info = {}
            for router_name, router_data in config.items():
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
        
        # Отримуємо список роутерів
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
            
            callback_data = f"access_manage_{router_name}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # Додаємо кнопки для роботи з кешем
        keyboard.add(
            InlineKeyboardButton("🔄 Оновити кеш", callback_data="access_refresh_cache"),
            InlineKeyboardButton("📊 Статистика", callback_data="access_stats")
        )
        
        return keyboard
    
    def create_router_management_keyboard(self, router_name: str) -> InlineKeyboardMarkup:
        """Створює клавіатуру для управління конкретним роутером - 3 кнопки"""
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        # Отримуємо список користувачів для цього роутера
        success, users = self.get_router_users(router_name)
        users_count = len(users) if success else 0
        
        # Отримуємо основну інформацію про роутер
        routers = self.router_manager.get_routers()
        router_info = routers.get(router_name, {})
        router_ip = router_info.get('ip', 'N/A')
        
        # 3 основні кнопки як запитав користувач
        keyboard.add(
            InlineKeyboardButton(f"👥 Активні користувачі ({users_count})", callback_data=f"access_view_users_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➕ Додати користувача", callback_data=f"access_add_user_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("➖ Видалити користувача", callback_data=f"access_remove_user_{router_name}")
        )
        keyboard.add(
            InlineKeyboardButton("🔙 Назад до списку роутерів", callback_data="access_main_menu")
        )
        
        return keyboard
    
    def create_router_selection_keyboard(self, action: str) -> InlineKeyboardMarkup:
        """Створює клавіатуру для вибору роутера"""
        routers = self.router_manager.get_routers()
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        for router_name, router_data in routers.items():
            # Пропускаємо секцію адміністраторів та інші не-роутери
            if router_name == 'admins' or not isinstance(router_data, dict):
                continue
            
            # Отримуємо додаткову інформацію про роутер
            ip = router_data.get('ip', 'N/A')
            users_count = len(router_data.get('allowed_users', []))
            
            # Створюємо текст кнопки з інформацією
            button_text = f"🌐 {router_name}\n📡 {ip} | 👥 {users_count}"
            
            callback_data = f"access_{action}_{router_name}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="access_main_menu"))
        
        return keyboard
    
    def create_general_info_keyboard(self) -> InlineKeyboardMarkup:
        """Створює клавіатуру для загальної інформації"""
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        keyboard.add(
            InlineKeyboardButton("📋 Список всіх користувачів", callback_data="access_list_all_users"),
            InlineKeyboardButton("🌐 Інформація про всі роутери", callback_data="access_all_routers_info")
        )
        keyboard.add(
            InlineKeyboardButton("🔙 Назад до меню", callback_data="access_main_menu")
        )
        
        return keyboard
    
    def validate_user_id(self, user_id: str) -> bool:
        """Валідує ID користувача"""
        try:
            # Перевіряємо, чи є це число
            int(user_id)
            # Перевіряємо довжину (Telegram ID зазвичай 7-10 цифр)
            return 7 <= len(user_id) <= 10
        except ValueError:
            return False
    
    def get_user_access_summary(self, user_id: str) -> str:
        """Отримує зведення доступу користувача"""
        routers = self.router_manager.get_routers()
        user_routers = []
        
        for router_name, router_data in routers.items():
            # Пропускаємо секцію адміністраторів та інші не-роутери
            if router_name == 'admins' or not isinstance(router_data, dict):
                continue
            
            if user_id in router_data.get('allowed_users', []):
                user_routers.append(router_name)
        
        if not user_routers:
            return f"Користувач {user_id} не має доступу до жодного роутера"
        
        return f"Користувач {user_id} має доступ до роутерів:\n" + "\n".join([f"• {router}" for router in user_routers]) 