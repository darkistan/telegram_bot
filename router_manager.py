import json
import logging
from typing import Dict, List, Optional, Any
from constants import MESSAGES, LOG_MESSAGES

class RouterManager:
    """Клас для управління роутерами з кешуванням даних"""
    
    def __init__(self, config_file: str = 'routers.json'):
        self.config_file = config_file
        self._routers_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 хвилин TTL для кешу
        
    def _load_routers_from_file(self) -> Dict[str, Any]:
        """Завантажує роутери з файлу"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                routers = json.load(file)
                logging.info(LOG_MESSAGES['routers_loaded'].format(routers))
                return routers
        except FileNotFoundError:
            logging.error(f"Файл {self.config_file} не знайдено")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Помилка парсингу JSON у файлі {self.config_file}: {e}")
            return {}
        except Exception as e:
            logging.error(f"Невідома помилка при завантаженні {self.config_file}: {e}")
            return {}
    
    def _is_cache_valid(self) -> bool:
        """Перевіряє, чи є кеш актуальним"""
        import time
        current_time = time.time()
        return (self._routers_cache is not None and 
                current_time - self._cache_timestamp < self._cache_ttl)
    
    def get_routers(self, force_reload: bool = False) -> Dict[str, Any]:
        """Отримує роутери з кешу або файлу"""
        if force_reload or not self._is_cache_valid():
            self._routers_cache = self._load_routers_from_file()
            import time
            self._cache_timestamp = time.time()
        
        return self._routers_cache
    
    def get_router(self, router_name: str) -> Optional[Dict[str, Any]]:
        """Отримує конкретний роутер за назвою"""
        routers = self.get_routers()
        return routers.get(router_name)
    
    def user_has_access(self, user_id: int, router_name: str) -> bool:
        """Перевіряє, чи має користувач доступ до роутера"""
        router = self.get_router(router_name)
        if not router:
            return False
        
        allowed_users = router.get('allowed_users', [])
        return str(user_id) in allowed_users
    
    def get_user_routers(self, user_id: int) -> List[str]:
        """Отримує список роутерів, до яких має доступ користувач"""
        routers = self.get_routers()
        user_routers = []
        
        for router_name, router_data in routers.items():
            if self.user_has_access(user_id, router_name):
                user_routers.append(router_name)
        
        return user_routers
    
    def get_router_scripts(self, router_name: str) -> List[str]:
        """Отримує список скриптів для конкретного роутера"""
        router = self.get_router(router_name)
        if not router:
            return []
        
        return router.get('scripts', [])
    
    def validate_script_password(self, router_name: str, password: str) -> bool:
        """Перевіряє пароль для виконання скрипта"""
        router = self.get_router(router_name)
        if not router:
            return False
        
        return password == router.get('script_password')
    
    def get_router_connection_info(self, router_name: str) -> Optional[Dict[str, Any]]:
        """Отримує інформацію для підключення до роутера"""
        router = self.get_router(router_name)
        if not router:
            return None
        
        return {
            'ip': router.get('ip'),
            'username': router.get('username'),
            'ssh_password': router.get('ssh_password'),
            'ssh_port': router.get('ssh_port', 22)
        }
    
    def clear_cache(self):
        """Очищає кеш роутерів"""
        self._routers_cache = None
        self._cache_timestamp = 0
        logging.info("Кеш роутерів очищено")
    
    def reload_routers(self):
        """Примусово перезавантажує роутери з файлу"""
        self.clear_cache()
        return self.get_routers(force_reload=True) 