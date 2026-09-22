"""Health check endpoint."""

import time
from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/api/health")
async def health_check():
    """Return a basic health check response."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": round(time.time() - _start_time, 2),
        "service": "SpliceTracker",
        "version": "1.0.0",
    }
