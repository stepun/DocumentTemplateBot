import os
from typing import Set
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.admin_password = os.getenv("ADMIN_PASSWORD", "default_password")
        self.authenticated_users: Set[int] = set()

    def authenticate(self, user_id: int, password: str) -> bool:
        """Аутентифицировать пользователя"""
        if password == self.admin_password:
            self.authenticated_users.add(user_id)
            logger.info(f"Пользователь {user_id} успешно аутентифицирован")
            return True
        logger.warning(f"Неудачная попытка аутентификации пользователя {user_id}")
        return False

    def is_authenticated(self, user_id: int) -> bool:
        """Проверить, аутентифицирован ли пользователь"""
        return user_id in self.authenticated_users

    def logout(self, user_id: int):
        """Выйти из системы"""
        self.authenticated_users.discard(user_id)
        logger.info(f"Пользователь {user_id} вышел из системы")

    def require_auth(self, func):
        """Декоратор для проверки аутентификации"""
        async def wrapper(*args, **kwargs):
            # Получаем user_id из аргументов (обычно message.from_user.id)
            message = args[0] if args else None
            if not message or not hasattr(message, 'from_user'):
                return await message.answer("❌ Ошибка аутентификации")

            if not self.is_authenticated(message.from_user.id):
                return await message.answer(
                    "🔐 Доступ запрещен. Введите команду /login <пароль> для входа в систему."
                )

            return await func(*args, **kwargs)
        return wrapper