
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from back.config import settings


# ============================================================
# НАСТРОЙКИ БЕЗОПАСНОСТИ
# ============================================================

# Секретный ключ JWT из .env
SECRET_KEY = settings.jwt_secret_key

# Алгоритм создания JWT
ALGORITHM = "HS256"

# Время жизни токена в минутах
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ============================================================
# ХЕШИРОВАНИЕ ПАРОЛЕЙ
# ============================================================

# Создаём инструмент для хеширования паролей
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Создаёт хеш пароля.
    """

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Проверяет пароль относительно сохранённого хеша.
    """

    try:
        return password_hasher.verify(password_hash, password)

    except (VerifyMismatchError, VerificationError):
        return False


# ============================================================
# JWT — СОЗДАНИЕ ТОКЕНА
# ============================================================

def create_access_token(user_id: int, role: str) -> str:
    """
    Создаёт JWT-токен пользователя.
    """

    current_time = datetime.now(timezone.utc)

    expire_time = current_time + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": current_time,
        "exp": expire_time
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# ============================================================
# JWT — ПРОВЕРКА ТОКЕНА
# ============================================================

def decode_access_token(token: str) -> dict | None:
    """
    Проверяет JWT-токен и возвращает его данные.

    Если токен недействителен или просрочен,
    возвращает None.
    """

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except jwt.InvalidTokenError:
        return None
