from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from back.config import settings
from pathlib import Path

# Создаём директорию для базы данных,
database_path = settings.database_url.replace("sqlite:///", "")

Path(database_path).parent.mkdir(parents=True, exist_ok=True)

# Создаём подключение к базе данных
engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False
    }
)

# Фабрика сессий базы данных
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Базовый класс моделей
class Base(DeclarativeBase):
    pass

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
