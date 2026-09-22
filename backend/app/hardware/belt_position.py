"""Belt position tracking providers.

Tracks the linear position of the conveyor belt and identifies the
nearest splice at any given moment.  The simulation provider models
continuous forward motion with wrap-around at the belt length.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BeltPositionProvider(ABC):
    """Abstract belt-position / encoder interface."""

    @abstractmethod
    async def get_position(self) -> Dict[str, Any]:
        """Return the current belt position and nearest splice info.

        Returns:
            Dict with ``position``, ``belt_id``, ``nearest_splice_id``,
            ``nearest_splice_distance``, ``direction``, ``speed``,
            ``is_estimated``, ``timestamp``.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` when the position source is available."""


# ---------------------------------------------------------------------------
# Simulation provider
# ---------------------------------------------------------------------------


class SimulationBeltPositionProvider(BeltPositionProvider):
    """Simulates belt position by integrating a constant speed over time.

    Splices are evenly distributed along the belt.
    """

    def __init__(
        self,
        belt_speed: float = 2.0,
        belt_length: float = 100.0,
        num_splices: int = 5,
    ) -> None:
        self.belt_speed = belt_speed  # m/s
        self.belt_length = belt_length  # m
        self._splices = self._generate_splice_positions(num_splices)
        self._running = False
        self._start_time: Optional[float] = None

    # -- splice layout -------------------------------------------------------

    @staticmethod
    def _generate_splice_positions(count: int) -> List[Dict[str, Any]]:
        """Evenly space *count* splices along the belt."""
        splices: List[Dict[str, Any]] = []
        if count <= 0:
            return splices
        spacing = 100.0 / count  # positions are normalised later
        for i in range(count):
            splices.append(
                {
                    "splice_id": f"SPL-{i + 1:03d}",
                    "position": round(spacing * (i + 0.5), 2),
                    "name": f"Splice {i + 1}",
                }
            )
        return splices

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._start_time = time.time()
        logger.info(
            "SimulationBeltPositionProvider started (speed=%.1f m/s, length=%.1f m, splices=%d)",
            self.belt_speed,
            self.belt_length,
            len(self._splices),
        )

    async def stop(self) -> None:
        self._running = False
        logger.info("SimulationBeltPositionProvider stopped")

    def is_connected(self) -> bool:
        return self._running

    # -- position calculation ------------------------------------------------

    async def get_position(self) -> Dict[str, Any]:
        now = time.time()
        if not self._running or self._start_time is None:
            return {
                "position": 0.0,
                "belt_id": "BELT-001",
                "nearest_splice_id": None,
                "nearest_splice_distance": None,
                "direction": "forward",
                "speed": 0.0,
                "is_estimated": True,
                "timestamp": now,
            }

        elapsed = now - self._start_time
        position = (self.belt_speed * elapsed) % self.belt_length
        position = round(position, 4)

        # Find nearest splice
        nearest_id: Optional[str] = None
        nearest_distance: Optional[float] = None
        for sp in self._splices:
            # Shortest distance on a circular belt
            raw_dist = abs(position - sp["position"])
            dist = min(raw_dist, self.belt_length - raw_dist)
            if nearest_distance is None or dist < nearest_distance:
                nearest_distance = round(dist, 4)
                nearest_id = sp["splice_id"]

        return {
            "position": position,
            "belt_id": "BELT-001",
            "nearest_splice_id": nearest_id,
            "nearest_splice_distance": nearest_distance,
            "direction": "forward",
            "speed": self.belt_speed,
            "is_estimated": False,
            "timestamp": now,
        }

    # -- accessors -----------------------------------------------------------

    def get_splice_positions(self) -> List[Dict[str, Any]]:
        """Return the list of configured splice positions."""
        return list(self._splices)


# ---------------------------------------------------------------------------
# Real hardware provider (stub)
# ---------------------------------------------------------------------------


class EncoderBeltPositionProvider(BeltPositionProvider):
    """Interface for a real rotary encoder measuring belt position.

    Returns safe defaults when the hardware is not connected.
    """

    def __init__(
        self,
        pin_a: int = 23,
        pin_b: int = 24,
        pulses_per_rev: int = 1024,
        wheel_circumference: float = 0.314,
    ) -> None:
        self._pin_a = pin_a
        self._pin_b = pin_b
        self._pulses_per_rev = pulses_per_rev
        self._wheel_circumference = wheel_circumference
        self._connected = False
        self._pulse_count = 0
        self._last_time: Optional[float] = None
        logger.info(
            "EncoderBeltPositionProvider configured (pins=%d/%d, ppr=%d)",
            pin_a,
            pin_b,
            pulses_per_rev,
        )

    async def start(self) -> None:
        """Attempt to initialise the encoder GPIO pins."""
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self._pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self._pin_a, GPIO.BOTH, callback=self._encoder_callback
            )
            self._connected = True
            self._last_time = time.time()
            logger.info("Encoder ready on GPIO %d/%d", self._pin_a, self._pin_b)
        except Exception:
            self._connected = False
            logger.warning("Could not initialise encoder; returning default positions")

    async def stop(self) -> None:
        if self._connected:
            try:
                import RPi.GPIO as GPIO  # type: ignore[import-untyped]
                GPIO.remove_event_detect(self._pin_a)
                GPIO.cleanup([self._pin_a, self._pin_b])
            except Exception:
                logger.exception("Error cleaning up encoder GPIO")
        self._connected = False

    def _encoder_callback(self, channel: int) -> None:
        """Called on each encoder pulse (runs in GPIO thread)."""
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            b_val = GPIO.input(self._pin_b)
            if b_val:
                self._pulse_count += 1
            else:
                self._pulse_count -= 1
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._connected

    async def get_position(self) -> Dict[str, Any]:
        now = time.time()
        if not self._connected:
            return {
                "position": 0.0,
                "belt_id": "BELT-001",
                "nearest_splice_id": None,
                "nearest_splice_distance": None,
                "direction": "forward",
                "speed": 0.0,
                "is_estimated": True,
                "timestamp": now,
                "error": "encoder_not_connected",
            }

        revolutions = self._pulse_count / self._pulses_per_rev
        position = revolutions * self._wheel_circumference

        # Speed estimation
        speed = 0.0
        if self._last_time is not None:
            dt = now - self._last_time
            if dt > 0:
                speed = abs(position) / dt  # rough estimate
        self._last_time = now

        direction = "forward" if self._pulse_count >= 0 else "reverse"

        return {
            "position": round(position, 4),
            "belt_id": "BELT-001",
            "nearest_splice_id": None,
            "nearest_splice_distance": None,
            "direction": direction,
            "speed": round(speed, 4),
            "is_estimated": False,
            "timestamp": now,
        }
