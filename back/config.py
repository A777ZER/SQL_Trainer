
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Корневая директория проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Директория Backend
BACK_DIR = PROJECT_ROOT / "back"

# Директория Frontend
FRONT_DIR = PROJECT_ROOT / "front"


class Settings(BaseSettings):
    # Название приложения
    app_name: str = "SQL Trainer"

    # Секретный ключ JWT
    jwt_secret_key: str = Field(min_length=32)

    # Основная база данных
    database_url: str = (
        f"sqlite:///{(BACK_DIR / 'data' / 'sql_trainer.db').as_posix()}"
    )

    # Путь к учебным заданиям
    exercises_dir: Path = BACK_DIR / "exercises"

    # Путь к собранному Frontend
    frontend_dist_dir: Path = FRONT_DIR / "dist"

    # Настройки загрузки переменных окружения
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Создаём единый объект настроек
settings = Settings()
