"""FastAPI application entry point for SpliceTracker."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import (
    alerts_router,
    analytics_router,
    config_router,
    health_router,
    inspections_router,
    simulation_router,
    splices_router,
    system_router,
    websocket_router,
)
from .api.websocket import ConnectionManager
from .config import get_settings 
from .core.events import EventBus
from .core.logging_config import setup_logging
from .database.database import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler: startup and shutdown logic."""
    settings = get_settings()

    # 1. Logging
    setup_logging(log_level=settings.LOG_LEVEL, logs_dir=str(settings.logs_dir))
    logger.info("SpliceTracker starting up")

    # 2. Database
    await init_db()
    logger.info("Database initialized")

    # 3. Event bus
    bus = EventBus.get_instance()
    logger.info("Event bus ready (%d event types)", len(bus._subscribers))

    # 4. WebSocket heartbeat
    ws_manager = ConnectionManager.get_instance()
    await ws_manager.start_heartbeat()
    logger.info("WebSocket heartbeat started (interval=%ds)", settings.WS_HEARTBEAT)

    # 5. Auto-start simulation if enabled
    sim_task = None
    if settings.SIMULATION_MODE:
        logger.info("SIMULATION_MODE is enabled — starting simulation")
        from .api.simulation import _run_simulation
        from .api import simulation as sim_module
        sim_task = asyncio.create_task(
            _run_simulation(splice_count=5, interval=10.0, anomaly_prob=0.15)
        )
        sim_module._simulation_task = sim_task

    # Ensure frames directory exists for static file serving
    frames_dir = settings.frames_dir
    logger.info("Frames directory: %s", frames_dir)

    logger.info("SpliceTracker ready")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────
    logger.info("SpliceTracker shutting down")

    # Stop simulation if running
    if sim_task and not sim_task.done():
        from .api import simulation as sim_module
        sim_module._simulation_running = False
        sim_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass

    # Stop heartbeat
    await ws_manager.stop_heartbeat()

    # Close DB
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="SpliceTracker",
        description="Industrial conveyor-belt splice monitoring system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configurable in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(health_router)
    app.include_router(splices_router)
    app.include_router(inspections_router)
    app.include_router(alerts_router)
    app.include_router(analytics_router)
    app.include_router(config_router)
    app.include_router(simulation_router)
    app.include_router(system_router)
    app.include_router(websocket_router)

    # Static files for frame serving
    frames_path = Path("data/frames")
    frames_path.mkdir(parents=True, exist_ok=True)
    app.mount("/frames", StaticFiles(directory=str(frames_path)), name="frames")

    return app


app = create_app()
