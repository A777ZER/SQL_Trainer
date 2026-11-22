from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from back.config import settings
from back.database import Base
from back import models


# Конфигурация Alembic
config = context.config

# Настраиваем логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Указываем метаданные моделей SQLAlchemy
target_metadata = Base.metadata

# Получаем URL основной базы данных
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%")
)


# ============================================================
# МИГРАЦИИ В РЕЖИМЕ OFFLINE
# ============================================================

def run_migrations_offline() -> None:
    """
    Запускает миграции без создания подключения к базе данных.
    """

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# МИГРАЦИИ В РЕЖИМЕ ONLINE
# ============================================================

def run_migrations_online() -> None:
    """
    Запускает миграции с подключением к базе данных.
    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ============================================================
# ВЫБОР РЕЖИМА ЗАПУСКА
# ============================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

