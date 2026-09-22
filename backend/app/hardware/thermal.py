"""Thermal sensor providers for splice temperature monitoring.

Includes a simulation provider that generates realistic temperature
readings with injectable thermal anomalies and a stub for real
serial/USB thermal cameras or IR sensors.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ThermalProvider(ABC):
    """Abstract thermal sensor interface."""

    @abstractmethod
    async def read(self) -> Dict[str, Any]:
        """Take a single thermal reading.

        Returns:
            Dict with at least ``temperature``, ``baseline``,
            ``delta_temperature``, ``rate_of_change``,
            ``thermal_anomaly_score``, ``hotspot_location``, ``timestamp``.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` when the sensor is ready."""


# ---------------------------------------------------------------------------
# Simulation provider
# ---------------------------------------------------------------------------


class SimulationThermalProvider(ThermalProvider):
    """Generates synthetic thermal readings around a configurable baseline.

    When an anomaly is active the temperature rises proportionally to the
    anomaly intensity (up to +15 degrees Celsius).
    """

    def __init__(self, baseline: float = 36.7) -> None:
        self.baseline = baseline
        self.noise_std = 0.3
        self._rng = np.random.default_rng()
        self._anomaly_active = False
        self._anomaly_intensity: float = 0.0

        # History of (unix_timestamp, temperature)
        self.history: deque[Tuple[float, float]] = deque(maxlen=100)
        self._connected = True

    # -- lifecycle -----------------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    # -- anomaly control -----------------------------------------------------

    def set_anomaly(self, active: bool, intensity: float = 0.5) -> None:
        """Enable or disable a thermal anomaly.

        Args:
            active: Whether the anomaly is active.
            intensity: Strength in ``[0, 1]`` (maps to 0-15 extra degrees).
        """
        self._anomaly_active = active
        self._anomaly_intensity = float(np.clip(intensity, 0.0, 1.0))

    # -- reading -------------------------------------------------------------

    async def read(self) -> Dict[str, Any]:
        # Small delay to simulate sensor sampling latency
        await asyncio.sleep(0.02)

        now = time.time()

        # Base temperature with Gaussian noise
        temperature = self.baseline + self._rng.normal(0, self.noise_std)

        # Inject anomaly heat
        if self._anomaly_active:
            temperature += self._anomaly_intensity * 15.0

        temperature = round(float(temperature), 2)

        # Delta from baseline
        delta_temperature = round(temperature - self.baseline, 2)

        # Rate of change (degrees per second)
        rate_of_change = 0.0
        if len(self.history) >= 2:
            prev_ts, prev_temp = self.history[-1]
            dt = now - prev_ts
            if dt > 0:
                rate_of_change = round((temperature - prev_temp) / dt, 4)

        # Record history
        self.history.append((now, temperature))

        # Anomaly score: 0-1 based on deviation from baseline.
        # Use a sigmoid-style mapping: small deviations stay near 0,
        # large deviations saturate toward 1.
        abs_delta = abs(delta_temperature)
        # 5 degrees above baseline -> score ~0.76; 10 -> ~0.95
        thermal_anomaly_score = round(float(1.0 - np.exp(-0.3 * abs_delta)), 4)

        # Hotspot location (only meaningful when anomaly is active)
        hotspot_location: Optional[Dict[str, float]] = None
        if self._anomaly_active:
            hotspot_location = {
                "x": round(float(self._rng.uniform(0.2, 0.8)), 3),
                "y": round(float(self._rng.uniform(0.35, 0.65)), 3),
            }

        return {
            "temperature": temperature,
            "baseline": self.baseline,
            "delta_temperature": delta_temperature,
            "rate_of_change": rate_of_change,
            "thermal_anomaly_score": thermal_anomaly_score,
            "hotspot_location": hotspot_location,
            "timestamp": now,
        }

    # -- trend ---------------------------------------------------------------

    def get_trend(self) -> List[Tuple[float, float]]:
        """Return recent ``(timestamp, temperature)`` tuples."""
        return list(self.history)


# ---------------------------------------------------------------------------
# Real hardware provider (stub)
# ---------------------------------------------------------------------------


class RealThermalProvider(ThermalProvider):
    """Interface for a real thermal sensor connected via serial or USB.

    This provider is intentionally a skeleton: the ``read`` method returns
    safe default values when the sensor is not connected so that the rest
    of the pipeline can proceed in a degraded state.
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baud_rate: int = 115200) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._connected = False
        self._serial: Any = None
        logger.info("RealThermalProvider configured for %s @ %d baud", port, baud_rate)

    async def start(self) -> None:
        """Attempt to open the serial connection."""
        try:
            import serial  # type: ignore[import-untyped]
            self._serial = serial.Serial(self._port, self._baud_rate, timeout=1)
            self._connected = True
            logger.info("Thermal sensor connected on %s", self._port)
        except Exception:
            self._connected = False
            logger.warning(
                "Could not connect to thermal sensor on %s; returning default readings",
                self._port,
            )

    async def stop(self) -> None:
        """Close the serial connection."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                logger.exception("Error closing thermal serial port")
            finally:
                self._serial = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def read(self) -> Dict[str, Any]:
        now = time.time()
        if not self._connected or self._serial is None:
            return {
                "temperature": 0.0,
                "baseline": 0.0,
                "delta_temperature": 0.0,
                "rate_of_change": 0.0,
                "thermal_anomaly_score": 0.0,
                "hotspot_location": None,
                "timestamp": now,
                "error": "sensor_not_connected",
            }

        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, self._serial.readline)
            line = raw.decode("utf-8", errors="replace").strip()
            temperature = float(line)
            return {
                "temperature": temperature,
                "baseline": 0.0,
                "delta_temperature": temperature,
                "rate_of_change": 0.0,
                "thermal_anomaly_score": 0.0,
                "hotspot_location": None,
                "timestamp": now,
            }
        except Exception as exc:
            logger.error("Thermal read error: %s", exc)
            return {
                "temperature": 0.0,
                "baseline": 0.0,
                "delta_temperature": 0.0,
                "rate_of_change": 0.0,
                "thermal_anomaly_score": 0.0,
                "hotspot_location": None,
                "timestamp": now,
                "error": str(exc),
            }
