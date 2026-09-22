"""Shared test fixtures for SpliceTracker backend tests."""

import asyncio
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure the backend package is importable
_backend_root = Path(__file__).resolve().parent.parent.parent  # /workshop/SpliceTracker
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.app.database.models import Base
from backend.app.core.events import EventBus, EventType
from backend.app.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite engine with all tables created."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Provide a fresh async session bound to the in-memory engine."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def event_bus():
    """Provide a fresh EventBus instance (not the singleton)."""
    bus = EventBus()
    return bus


@pytest.fixture
def test_config():
    """Return a Settings instance configured for testing."""
    return Settings(
        SIMULATION_MODE=True,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
