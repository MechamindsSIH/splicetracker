"""Multi-sensor signal synchronisation for splice monitoring.

Collects observations from vision, thermal, conductive, and mechanical
sensors and groups them into time-aligned windows so that downstream
fusion logic can combine correlated measurements.
"""

import time
from typing import Optional


class SignalSynchronizer:
    """Synchronises observations from multiple sensor modalities within a
    configurable time window.
    """

    def __init__(self, window_ms: int = 500):
        self.window_ms: int = window_ms
        self.pending: dict[str, tuple[dict, float]] = {}
        self.required_sensors: set[str] = {"vision", "thermal", "conductive", "mechanical"}
        self.minimum_sensors: int = 2  # minimum distinct sensors to form a valid window

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_observation(self, sensor_type: str, data: dict, timestamp: float) -> None:
        """Register a new sensor observation.

        Parameters
        ----------
        sensor_type : str
            One of ``"vision"``, ``"thermal"``, ``"conductive"``,
            ``"mechanical"``.
        data : dict
            Processed sensor payload (plain dict).
        timestamp : float
            POSIX timestamp of the observation.
        """
        self.pending[sensor_type] = (data, timestamp)

    def get_synchronized_window(self) -> Optional[dict]:
        """Attempt to build a synchronized measurement window.

        Returns a window dict when at least ``minimum_sensors``
        observations fall within ``window_ms`` of each other.  Stale
        observations older than ``2 * window_ms`` relative to the most
        recent reading are pruned automatically.

        Returns ``None`` when a valid window cannot be formed.
        """
        if len(self.pending) < self.minimum_sensors:
            return None

        # Prune stale entries -- anything older than 2x the window
        # relative to the newest observation.
        if self.pending:
            newest_ts = max(ts for _, ts in self.pending.values())
            stale_cutoff = newest_ts - (2.0 * self.window_ms / 1000.0)
            stale_keys = [
                k for k, (_, ts) in self.pending.items() if ts < stale_cutoff
            ]
            for k in stale_keys:
                del self.pending[k]

        if len(self.pending) < self.minimum_sensors:
            return None

        # Determine the time span of all pending observations
        timestamps = {k: ts for k, (_, ts) in self.pending.items()}
        all_ts = list(timestamps.values())
        earliest = min(all_ts)
        latest = max(all_ts)
        span_ms = (latest - earliest) * 1000.0

        # All observations must fit inside the window
        if span_ms > self.window_ms:
            # Try to form the largest subset that fits.
            # Greedy: anchor on the newest observation and include
            # everything within window_ms before it.
            cutoff = latest - (self.window_ms / 1000.0)
            in_window = {
                k: (data, ts)
                for k, (data, ts) in self.pending.items()
                if ts >= cutoff
            }
            if len(in_window) < self.minimum_sensors:
                return None

            sensors = {k: data for k, (data, _) in in_window.items()}
            ts_map = {k: ts for k, (_, ts) in in_window.items()}
        else:
            sensors = {k: data for k, (data, _) in self.pending.items()}
            ts_map = dict(timestamps)

        window_start = min(ts_map.values())
        window_end = max(ts_map.values())
        duration_ms = (window_end - window_start) * 1000.0

        result = {
            "sensors": sensors,
            "timestamps": ts_map,
            "window_start": window_start,
            "window_end": window_end,
            "window_duration_ms": round(duration_ms, 2),
            "sensor_count": len(sensors),
            "complete": self.required_sensors.issubset(set(sensors.keys())),
        }

        # Clear the consumed observations so the next window starts fresh
        for k in list(sensors.keys()):
            self.pending.pop(k, None)

        return result

    def clear(self) -> None:
        """Discard all pending observations."""
        self.pending.clear()
