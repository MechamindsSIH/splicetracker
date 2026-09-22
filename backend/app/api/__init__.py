from .health import router as health_router
from .splices import router as splices_router
from .inspections import router as inspections_router
from .alerts import router as alerts_router
from .analytics import router as analytics_router
from .config_routes import router as config_router
from .simulation import router as simulation_router
from .system import router as system_router
from .websocket import router as websocket_router

__all__ = [
    "health_router", "splices_router", "inspections_router",
    "alerts_router", "analytics_router", "config_router",
    "simulation_router", "system_router", "websocket_router",
]
