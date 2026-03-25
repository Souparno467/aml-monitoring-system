"""
Alembic Environment
--------------------
Supports both:
  - Online mode  : alembic upgrade head  (against live DB)
  - Offline mode : alembic upgrade head --sql  (generates SQL script)

Async-compatible via asyncpg / SQLAlchemy async engine.
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# â”€â”€ Load app config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# We import settings here so DATABASE_URL is always resolved from .env
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from app.config import settings

# Import all models so Alembic can detect schema changes via autogenerate
from app.db.base import Base  # noqa: F401 â€” registers Base metadata
from app.models.user         import User          # noqa: F401
from app.models.transaction  import Transaction   # noqa: F401
from app.models.alert        import Alert         # noqa: F401
from app.models.risk_score   import RiskScore     # noqa: F401
from app.models.pep_profile  import PEPProfile    # noqa: F401

# â”€â”€ Alembic config object â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
config = context.config

# Wire DATABASE_URL from settings (overrides alembic.ini placeholder)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for --autogenerate support
target_metadata = Base.metadata


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def include_object(object, name, type_, reflected, compare_to):
    """
    Exclude non-public schemas from autogenerate.
    Only migrate tables in the 'public' schema (or default schema).
    """
    if type_ == "table" and object.schema not in (None, "public"):
        return False
    return True


def run_migrations_offline() -> None:
    """
    Offline mode: write SQL to stdout / file without connecting to DB.
    Useful for generating migration scripts for DBA review.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        # Render ENUM drops/creates properly on PostgreSQL
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online mode: connect and apply migrations asynchronously."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,        # Don't pool during migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

