"""
migrations/env.py — Alembic environment configuration.

Reads DATABASE_URL from core.config (pydantic-settings),
converts asyncpg → psycopg2 for Alembic's sync driver,
and runs migrations.
"""

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure the project root is on sys.path so core.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

# ── Alembic Config object ─────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging (alembic.ini [loggers] section)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Inject DATABASE_URL from settings ─────────────────────────────────────
settings = get_settings()

# Alembic requires a synchronous driver — swap asyncpg → psycopg2
sync_url = settings.database_url.replace(
    "postgresql+asyncpg", "postgresql+psycopg2"
)
logger.info("Alembic using database: %s", sync_url.split("@")[-1])  # log host only

# ── Target metadata ───────────────────────────────────────────────────────
# We write raw SQL migrations, not ORM-based autogenerate.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates a database connection and runs migrations within a transaction.
    """
    from sqlalchemy import create_engine

    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
