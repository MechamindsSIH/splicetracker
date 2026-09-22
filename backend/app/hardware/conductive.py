"""Conductive continuity sensor providers for splice monitoring.

A conductive sensor detects whether the splice's conductive loop is
intact.  A break in continuity is a strong indicator of mechanical
splice failure.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ConductiveProvider(ABC):
    """Abstract conductive continuity sensor interface."""

    @abstractmethod
    async def read(self) -> Dict[str, Any]:
        """Take a single continuity reading.

        Returns:
            Dict with ``continuity``, ``previous_state``, ``transition``,
            ``duration_ms``, ``anomaly_score``, ``timestamp``.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` when the sensor is ready."""


# ---------------------------------------------------------------------------
# Simulation provider
# ---------------------------------------------------------------------------


class SimulationConductiveProvider(ConductiveProvider):
    """Simulates conductive continuity sensing with injectable breaks."""

    def __init__(self) -> None:
        self._continuity: bool = True
        self._previous_state: bool = True
        self._break_active: bool = False
        self._break_start_time: Optional[float] = None
        self._connected: bool = True
        self._last_read_time: Optional[float] = None

    # -- lifecycle -----------------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    # -- break injection -----------------------------------------------------

    def trigger_break(self) -> None:
        """Simulate a continuity break."""
        self._previous_state = self._continuity
        self._continuity = False
        self._break_active = True
        self._break_start_time = time.time()
        logger.info("Conductive break triggered")

    def restore_continuity(self) -> None:
        """Restore normal continuity after a break."""
        self._previous_state = self._continuity
        self._continuity = True
        self._break_active = False
        self._break_start_time = None
        logger.info("Conductive continuity restored")

    # -- reading -------------------------------------------------------------

    async def read(self) -> Dict[str, Any]:
        # Small delay to simulate sensor polling latency
        await asyncio.sleep(0.01)

        now = time.time()

        # Determine the transition label
        if self._continuity and self._previous_state:
            transition = "continuous"
        elif not self._continuity and self._previous_state:
            transition = "break_detected"
        elif not self._continuity and not self._previous_state:
            transition = "break_ongoing"
        else:
            # Was broken, now restored
            transition = "restored"

        # Duration since break started (milliseconds)
        duration_ms = 0.0
        if not self._continuity and self._break_start_time is not None:
            duration_ms = round((now - self._break_start_time) * 1000.0, 2)

        # Anomaly score
        anomaly_score = 1.0 if not self._continuity else 0.0

        # Map booleans to descriptive strings for previous_state
        prev_state_str = "continuous" if self._previous_state else "broken"

        # Advance state tracking for next read
        self._previous_state = self._continuity
        self._last_read_time = now

        return {
            "continuity": self._continuity,
            "previous_state": prev_state_str,
            "transition": transition,
            "duration_ms": duration_ms,
            "anomaly_score": anomaly_score,
            "timestamp": now,
        }


# ---------------------------------------------------------------------------
# Real hardware provider (stub)
# ---------------------------------------------------------------------------


class RealConductiveProvider(ConductiveProvider):
    """Interface for a real conductive continuity sensor connected via GPIO or serial.

    Returns safe default values when the sensor is not connected.
    """

    def __init__(self, pin: int = 17) -> None:
        self._pin = pin
        self._connected = False
        logger.info("RealConductiveProvider configured for GPIO pin %d", pin)

    async def start(self) -> None:
        """Attempt to initialise the GPIO pin."""
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._connected = True
            logger.info("Conductive sensor ready on GPIO %d", self._pin)
        except Exception:
            self._connected = False
            logger.warning(
                "Could not initialise GPIO %d for conductive sensor; returning defaults",
                self._pin,
            )

    async def stop(self) -> None:
        """Release GPIO resources."""
        if self._connected:
            try:
                import RPi.GPIO as GPIO  # type: ignore[import-untyped]
                GPIO.cleanup(self._pin)
            except Exception:
                logger.exception("Error cleaning up GPIO %d", self._pin)
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def read(self) -> Dict[str, Any]:
        now = time.time()
        if not self._connected:
            return {
                "continuity": True,
                "previous_state": "unknown",
                "transition": "unknown",
                "duration_ms": 0.0,
                "anomaly_score": 0.0,
                "timestamp": now,
                "error": "sensor_not_connected",
            }

        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            loop = asyncio.get_running_loop()
            value = await loop.run_in_executor(None, GPIO.input, self._pin)
            continuity = bool(value)
            return {
                "continuity": continuity,
                "previous_state": "unknown",
                "transition": "continuous" if continuity else "break_detected",
                "duration_ms": 0.0,
                "anomaly_score": 0.0 if continuity else 1.0,
                "timestamp": now,
            }
        except Exception as exc:
            logger.error("Conductive read error: %s", exc)
            return {
                "continuity": True,
                "previous_state": "unknown",
                "transition": "unknown",
                "duration_ms": 0.0,
                "anomaly_score": 0.0,
                "timestamp": now,
                "error": str(exc),
            }
