"""Thermal signal processing for conveyor-belt splice monitoring.

Maintains a rolling baseline of temperature readings and detects anomalies
based on deviation magnitude, rate of change, and trend consistency.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np


class ThermalProcessor:
    """Processes thermal sensor readings to detect splice overheating and
    anomalous temperature behaviour.
    """

    def __init__(self, baseline_window: int = 20):
        self.baseline_window: int = baseline_window
        self.readings: deque[dict] = deque(maxlen=baseline_window)
        self.baseline: Optional[float] = None

        # Tuning knobs
        self._delta_saturation: float = 15.0  # degrees C at which delta score maxes out
        self._rate_saturation: float = 2.0    # deg/s at which rate score maxes out
        self._consistency_window: int = 5     # recent readings to check for sustained trend

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, reading: dict) -> dict:
        """Process a single thermal reading and return an enriched result.

        Parameters
        ----------
        reading : dict
            Must contain at least ``"temperature"`` (float) and
            ``"timestamp"`` (float, POSIX seconds).  Additional keys
            (e.g. ``"sensor_id"``, ``"hotspot_location"``) are passed
            through unchanged.

        Returns
        -------
        dict
            Original fields plus computed analytics:
            ``processed_baseline``, ``processed_delta``,
            ``processed_rate_of_change``, ``processed_anomaly_score``,
            ``trend``, ``readings_count``.
        """
        temperature: float = float(reading["temperature"])
        timestamp: float = float(reading["timestamp"])

        # Store the new reading
        self.readings.append({"temperature": temperature, "timestamp": timestamp})

        # Update baseline (running mean over the window)
        temps = np.array([r["temperature"] for r in self.readings])
        self.baseline = float(np.mean(temps))

        # Delta from baseline
        delta = temperature - self.baseline

        # Rate of change via least-squares linear regression
        rate_of_change = self._compute_rate_of_change()

        # Trend classification
        trend = self._classify_trend(delta, rate_of_change)

        # Anomaly score
        anomaly_score = self._compute_anomaly_score(delta, rate_of_change)

        result = dict(reading)
        result.update({
            "processed_baseline": round(self.baseline, 4),
            "processed_delta": round(delta, 4),
            "processed_rate_of_change": round(rate_of_change, 6),
            "processed_anomaly_score": round(anomaly_score, 4),
            "trend": trend,
            "readings_count": len(self.readings),
        })
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_rate_of_change(self) -> float:
        """Fit a line through recent readings and return the slope (deg/s)."""
        n = len(self.readings)
        if n < 2:
            return 0.0

        timestamps = np.array([r["timestamp"] for r in self.readings])
        temps = np.array([r["temperature"] for r in self.readings])

        # Centre timestamps around their mean for numerical stability
        t_mean = np.mean(timestamps)
        t_centered = timestamps - t_mean

        denom = np.sum(t_centered ** 2)
        if denom < 1e-12:
            return 0.0

        slope = float(np.sum(t_centered * (temps - np.mean(temps))) / denom)
        return slope

    def _classify_trend(self, delta: float, rate: float) -> str:
        """Classify the current thermal trend.

        Returns one of: ``"stable"``, ``"rising"``, ``"falling"``,
        ``"spike"``.
        """
        n = len(self.readings)

        # A spike is a sudden large deviation that was not preceded by a
        # consistent trend in the same direction.
        if n >= 3:
            recent_temps = [r["temperature"] for r in list(self.readings)[-3:]]
            diffs = [recent_temps[i + 1] - recent_temps[i] for i in range(len(recent_temps) - 1)]

            # Spike: the most recent change is large and reversed direction
            if len(diffs) >= 2:
                if abs(diffs[-1]) > self._delta_saturation * 0.3 and (
                    (diffs[-1] > 0 and diffs[-2] < 0) or (diffs[-1] < 0 and diffs[-2] > 0)
                ):
                    return "spike"

        # Consistent direction check over the consistency window
        if n >= self._consistency_window:
            window = list(self.readings)[-self._consistency_window:]
            changes = [
                window[i + 1]["temperature"] - window[i]["temperature"]
                for i in range(len(window) - 1)
            ]
            rising = sum(1 for c in changes if c > 0)
            falling = sum(1 for c in changes if c < 0)
            total = len(changes)

            if rising >= total * 0.7 and rate > 0.01:
                return "rising"
            if falling >= total * 0.7 and rate < -0.01:
                return "falling"

        # Simpler check for fewer readings
        if abs(rate) > 0.05:
            return "rising" if rate > 0 else "falling"

        return "stable"

    def _compute_anomaly_score(self, delta: float, rate: float) -> float:
        """Compute a composite anomaly score in [0, 1].

        Components:
        - Delta magnitude (40 %): how far from baseline.
        - Rate of change (35 %): how fast the temperature is moving.
        - Consistency (25 %): is the recent trend sustained?
        """
        # Delta component
        delta_score = min(abs(delta) / self._delta_saturation, 1.0)

        # Rate component
        rate_score = min(abs(rate) / self._rate_saturation, 1.0)

        # Consistency component -- fraction of recent changes in the
        # same direction as the current delta
        consistency_score = 0.0
        n = len(self.readings)
        if n >= 3:
            window_size = min(n, self._consistency_window)
            window = list(self.readings)[-window_size:]
            changes = [
                window[i + 1]["temperature"] - window[i]["temperature"]
                for i in range(len(window) - 1)
            ]
            if changes:
                if delta >= 0:
                    same_dir = sum(1 for c in changes if c > 0)
                else:
                    same_dir = sum(1 for c in changes if c < 0)
                consistency_score = same_dir / len(changes)

        score = 0.40 * delta_score + 0.35 * rate_score + 0.25 * consistency_score
        return float(np.clip(score, 0.0, 1.0))
