"""Configuration read/update endpoints."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import Settings, get_settings
from ..core.schemas import ConfigResponse, ConfigUpdateRequest

router = APIRouter(prefix="/api/config", tags=["config"])

# We maintain a mutable runtime overlay so PUT changes take effect
# without restarting the server.  The canonical source remains .env.
_runtime_overrides: dict = {}


def _current_settings() -> Settings:
    """Build settings with any runtime overrides applied."""
    base = get_settings()
    for key, value in _runtime_overrides.items():
        if hasattr(base, key):
            object.__setattr__(base, key, value)
    return base


@router.get("", response_model=ConfigResponse)
async def get_config():
    """Return the current effective configuration."""
    s = _current_settings()
    return ConfigResponse(
        camera_index=s.CAMERA_INDEX,
        camera_width=s.CAMERA_WIDTH,
        camera_height=s.CAMERA_HEIGHT,
        camera_fps=s.CAMERA_FPS,
        thermal_enabled=s.THERMAL_ENABLED,
        conductive_enabled=s.CONDUCTIVE_ENABLED,
        mechanical_enabled=s.MECHANICAL_ENABLED,
        database_url=s.DATABASE_URL,
        belt_speed=s.BELT_SPEED,
        belt_length=s.BELT_LENGTH,
        simulation_mode=s.SIMULATION_MODE,
        log_level=s.LOG_LEVEL,
        ws_heartbeat=s.WS_HEARTBEAT,
        frame_buffer_size=s.FRAME_BUFFER_SIZE,
        event_window_ms=s.EVENT_WINDOW_MS,
    )


@router.put("", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest):
    """Update mutable configuration values at runtime.

    Only the fields present in the request body are updated.
    Camera and database settings are not mutable at runtime.
    """
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No configuration fields provided")

    allowed_keys = {
        "thermal_enabled": "THERMAL_ENABLED",
        "conductive_enabled": "CONDUCTIVE_ENABLED",
        "mechanical_enabled": "MECHANICAL_ENABLED",
        "belt_speed": "BELT_SPEED",
        "belt_length": "BELT_LENGTH",
        "simulation_mode": "SIMULATION_MODE",
        "log_level": "LOG_LEVEL",
        "ws_heartbeat": "WS_HEARTBEAT",
        "frame_buffer_size": "FRAME_BUFFER_SIZE",
        "event_window_ms": "EVENT_WINDOW_MS",
    }

    for api_key, env_key in allowed_keys.items():
        if api_key in updates:
            _runtime_overrides[env_key] = updates[api_key]

    return await get_config()
