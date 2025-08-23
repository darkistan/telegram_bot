from typing import Dict, Any, Optional
from constants import USER_STATES

class UserStateManager:
    """Клас для управління станом користувачів"""
    
    def __init__(self):
        self._user_states = {}
    
    def set_state(self, user_id: int, state: str, **kwargs):
        """Встановлює стан користувача з додатковими даними"""
        if user_id not in self._user_states:
            self._user_states[user_id] = {}
        
        self._user_states[user_id]['state'] = state
        self._user_states[user_id].update(kwargs)
    
    def get_state(self, user_id: int) -> Optional[str]:
        """Отримує поточний стан користувача"""
        user_data = self._user_states.get(user_id, {})
        return user_data.get('state')
    
    def get_user_data(self, user_id: int, key: str, default=None):
        """Отримує конкретне значення з даних користувача"""
        user_data = self._user_states.get(user_id, {})
        return user_data.get(key, default)
    
    def set_user_data(self, user_id: int, key: str, value: Any):
        """Встановлює значення для користувача"""
        if user_id not in self._user_states:
            self._user_states[user_id] = {}
        
        self._user_states[user_id][key] = value
    
    def is_in_state(self, user_id: int, state: str) -> bool:
        """Перевіряє, чи знаходиться користувач у конкретному стані"""
        return self.get_state(user_id) == state
    
    def clear_user_state(self, user_id: int):
        """Очищає стан користувача"""
        if user_id in self._user_states:
            del self._user_states[user_id]
    
    def get_all_user_data(self, user_id: int) -> Dict[str, Any]:
        """Отримує всі дані користувача"""
        return self._user_states.get(user_id, {}).copy()
    
    def set_waiting_for_router(self, user_id: int):
        """Встановлює стан очікування вибору роутера"""
        self.set_state(user_id, USER_STATES['waiting_for_router'])
    
    def set_waiting_for_script(self, user_id: int, router_name: str):
        """Встановлює стан очікування вибору скрипта"""
        self.set_state(user_id, USER_STATES['waiting_for_script'], router=router_name)
    
    def set_waiting_for_password(self, user_id: int, router_name: str, script: str):
        """Встановлює стан очікування введення пароля"""
        self.set_state(user_id, USER_STATES['waiting_for_password'], 
                      router=router_name, script=script)
    
    def set_waiting_for_confirmation(self, user_id: int, router_name: str, script: str):
        """Встановлює стан очікування підтвердження"""
        self.set_state(user_id, USER_STATES['waiting_for_confirmation'], 
                      router=router_name, script=script)
    
    def get_router_name(self, user_id: int) -> Optional[str]:
        """Отримує назву роутера з стану користувача"""
        return self.get_user_data(user_id, 'router')
    
    def get_script_name(self, user_id: int) -> Optional[str]:
        """Отримує назву скрипта з стану користувача"""
        return self.get_user_data(user_id, 'script')
    
    def has_router_and_script(self, user_id: int) -> bool:
        """Перевіряє, чи має користувач встановлені роутер та скрипт"""
        return (self.get_router_name(user_id) is not None and 
                self.get_script_name(user_id) is not None)
    
    def get_active_users_count(self) -> int:
        """Отримує кількість активних користувачів"""
        return len(self._user_states)
    
    def get_users_in_state(self, state: str) -> list:
        """Отримує список користувачів у конкретному стані"""
        users = []
        for user_id, user_data in self._user_states.items():
            if user_data.get('state') == state:
                users.append(user_id)
        return users 