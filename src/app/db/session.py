from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _engine, _SessionLocal
    if _engine is None or _SessionLocal is None:
        try:
            _engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
        except ModuleNotFoundError as exc:
            if settings.DATABASE_URL.startswith("sqlite+aiosqlite") and "aiosqlite" in str(exc):
                raise RuntimeError(
                    "SQLite async driver not installed. Run: pip install aiosqlite "
                    "(or set DATABASE_URL to a Postgres URL)."
                ) from exc
            raise
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine, _SessionLocal


async def init_db() -> None:
    """Initialize DB for local dev.

    - Always imports models so `Base.metadata` is populated.
    - If using SQLite, auto-creates tables on startup for a zero-setup demo.
    - If using Postgres, expects migrations (Alembic) to have been applied.
    """

    from app.db.base import Base

    # Ensure all models are imported and registered with Base.metadata.
    from app import models as _models  # noqa: F401
    from app.core import audit as _audit  # noqa: F401

    engine, _ = _ensure_engine()

    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, SessionLocal = _ensure_engine()
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
