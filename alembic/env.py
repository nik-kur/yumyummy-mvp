import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.db.base import Base
from app import models  # noqa  # чтобы Alembic увидел все модели

# Это объект конфигурации Alembic, даёт доступ к данным из alembic.ini
config = context.config

# Подставляем реальный URL БД из .env
config.set_main_option("sqlalchemy.url", settings.database_url)

# Настраиваем логирование (можно не трогать)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata всех наших моделей
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в offline-режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
