"""Tests for FastAPI API endpoints using httpx AsyncClient.

These tests use the FastAPI TestClient pattern with dependency overrides
to inject an in-memory database.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.database.models import (
    Base,
    Alert,
    AlertSeverity,
    AlertStatus,
    RiskLevel,
    Splice,
    SpliceCondition,
)
from backend.app.database.database import async_session as db_dependency
from backend.app.main import create_app


@pytest.fixture
async def test_app():
    """Create a test app with an in-memory database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )

    app = create_app()

    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[db_dependency] = override_session

    yield app, engine, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(test_app):
    """Provide an httpx AsyncClient for the test app."""
    app, engine, session_factory = test_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_factory


async def _seed_splice(session_factory, name="Splice-001", condition=SpliceCondition.GOOD):
    """Seed a splice into the test database and return its ID."""
    async with session_factory() as session:
        splice = Splice(
            name=name, belt_id="BELT-A", position=10.0,
            condition=condition, severity=0.0, confidence=1.0,
            risk_level=RiskLevel.LOW,
        )
        session.add(splice)
        await session.commit()
        return splice.id


async def _seed_alert(session_factory, splice_id, severity=AlertSeverity.WARNING):
    """Seed an alert into the test database."""
    async with session_factory() as session:
        alert = Alert(
            splice_id=splice_id, severity=severity,
            confidence=0.8, risk_score=0.6,
            reason="Test alert", status=AlertStatus.ACTIVE,
        )
        session.add(alert)
        await session.commit()
        return alert.id


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    async def test_health_endpoint(self, client):
        """Health endpoint returns 200 with healthy status."""
        ac, _ = client
        response = await ac.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "SpliceTracker"
        assert data["version"] == "1.0.0"
        assert "uptime_seconds" in data
        assert "timestamp" in data


class TestSplicesEndpoint:
    """Tests for the /api/splices endpoint."""

    async def test_get_splices_empty(self, client):
        """Returns empty list when no splices exist."""
        ac, _ = client
        response = await ac.get("/api/splices")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["splices"] == []

    async def test_get_splices_with_data(self, client):
        """Returns splices after seeding."""
        ac, session_factory = client
        await _seed_splice(session_factory, "Splice-A")
        await _seed_splice(session_factory, "Splice-B")

        response = await ac.get("/api/splices")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["splices"]) == 2

    async def test_get_splice_not_found(self, client):
        """Requesting a non-existent splice returns 404."""
        ac, _ = client
        response = await ac.get("/api/splices/9999")
        assert response.status_code == 404


class TestAlertsEndpoint:
    """Tests for the /api/alerts endpoint."""

    async def test_get_alerts_empty(self, client):
        """Returns empty list when no alerts exist."""
        ac, _ = client
        response = await ac.get("/api/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_alerts_with_data(self, client):
        """Returns alerts after seeding."""
        ac, session_factory = client
        splice_id = await _seed_splice(session_factory, "Splice-AlertTest")
        await _seed_alert(session_factory, splice_id, AlertSeverity.HIGH)

        response = await ac.get("/api/alerts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["severity"] == "HIGH"
        assert data[0]["status"] == "ACTIVE"


class TestAnalyticsEndpoint:
    """Tests for the /api/analytics endpoint."""

    async def test_get_analytics_empty(self, client):
        """Returns zeroed analytics when no data exists."""
        ac, _ = client
        response = await ac.get("/api/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_splices"] == 0
        assert data["total_inspections"] == 0
        assert data["total_alerts"] == 0

    async def test_get_analytics_with_data(self, client):
        """Analytics reflect seeded data."""
        ac, session_factory = client
        splice_id = await _seed_splice(session_factory, "Splice-Analytics")
        await _seed_alert(session_factory, splice_id)

        response = await ac.get("/api/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_splices"] == 1
        assert data["total_alerts"] == 1


class TestSystemStatus:
    """Tests for the /api/system/* endpoints."""

    async def test_system_status(self, client):
        """System status endpoint returns expected fields."""
        ac, _ = client
        response = await ac.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "uptime_seconds" in data
        assert "simulation_mode" in data
        assert "components" in data
        assert isinstance(data["components"], list)

    async def test_system_health(self, client):
        """System health endpoint returns expected fields."""
        ac, _ = client
        response = await ac.get("/api/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "database" in data
        assert "memory_usage_mb" in data
        assert "uptime_seconds" in data


class TestSimulationEndpoints:
    """Tests for the /api/simulation/* endpoints."""

    async def test_simulation_start(self, client):
        """Starting simulation returns success status."""
        ac, _ = client
        response = await ac.post(
            "/api/simulation/start",
            json={"splice_count": 2, "inspection_interval_seconds": 60.0, "anomaly_probability": 0.1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["splice_count"] == 2

        # Clean up: stop simulation
        import asyncio
        await asyncio.sleep(0.1)
        stop_response = await ac.post("/api/simulation/stop")
        # May return 200 or 409 depending on timing
        assert stop_response.status_code in (200, 409)

    async def test_simulation_stop_when_not_running(self, client):
        """Stopping simulation when not running returns 409."""
        ac, _ = client
        # Reset simulation state
        from backend.app.api import simulation as sim_mod
        sim_mod._simulation_running = False
        sim_mod._simulation_task = None

        response = await ac.post("/api/simulation/stop")
        assert response.status_code == 409


class TestPipelineStatus:
    """Tests for the /api/pipeline/status endpoint."""

    async def test_pipeline_status(self, client):
        """Pipeline status endpoint returns expected structure."""
        ac, _ = client
        response = await ac.get("/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        assert "stages" in data
        assert "overall_status" in data
        assert isinstance(data["stages"], list)
        assert len(data["stages"]) > 0
        for stage in data["stages"]:
            assert "name" in stage
            assert "status" in stage
