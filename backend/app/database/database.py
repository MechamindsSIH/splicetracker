"""Async SQLAlchemy engine and session configuration."""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

_engine = None
_session_factory = None


def _get_database_url() -> str:
    """Resolve the async database URL from settings or environment."""
    raw_url = os.getenv("DATABASE_URL", "sqlite:///./data/splicetracker.db")
    if raw_url.startswith("sqlite:///"):
        return raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return raw_url


def _ensure_data_dir(url: str) -> None:
    """Create the parent directory for an SQLite database if needed."""
    if "sqlite" in url:
        # Extract the path portion after sqlite+aiosqlite:///
        parts = url.split("///", 1)
        if len(parts) == 2:
            db_path = Path(parts[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    """Return the global async engine, creating it on first call."""
    global _engine
    if _engine is None:
        url = _get_database_url()
        _ensure_data_dir(url)
        _engine = create_async_engine(
            url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False} if "sqlite" in url else {},
        )
    return _engine


def get_session_factory():
    """Return the global session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Convenience aliases
engine = property(lambda self: get_engine())


async def init_db() -> None:
    """Create all tables in the database."""
    eng = get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine and reset globals."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_session() -> AsyncSession:
    """Yield a new async session.  Usage:

        session = await get_session()
        async with session:
            ...
    """
    factory = get_session_factory()
    return factory()


# Alias used as FastAPI dependency
async def async_session():
    """FastAPI-compatible dependency that yields a session and closes it."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
