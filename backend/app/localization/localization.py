import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class LocalizationEngine:
    """Associates events with belt coordinates and splice positions.

    Works with a BeltPositionProvider to map sensor events to physical
    locations on the conveyor belt.
    """

    def __init__(self, belt_position_provider):
        """
        Args:
            belt_position_provider: A BeltPositionProvider instance (simulation or real)
                that has async get_position() -> dict method and is_connected() -> bool method
        """
        self.belt_position = belt_position_provider
        self.position_history = []  # list of recent position readings
        self.max_history = 100

    async def localize_event(self, event_data: dict) -> dict:
        """Get current belt position and associate with event.

        Steps:
        1. Get current position from belt_position_provider
        2. Record position in history
        3. Calculate position confidence based on provider state and consistency
        4. Merge position data with event metadata

        Args:
            event_data: dict with at least a 'splice_id' key, may have other event info

        Returns dict with:
            belt_id, splice_id, position, position_confidence, is_estimated,
            direction, speed, nearest_splice_id, nearest_splice_distance, timestamp
        """
        if event_data is None:
            event_data = {}

        splice_id = event_data.get("splice_id", "unknown")
        now = datetime.now(timezone.utc)

        # Attempt to get position from the belt position provider
        position_data = None
        provider_connected = False
        try:
            provider_connected = self.belt_position.is_connected()
            position_data = await self.belt_position.get_position()
        except Exception as exc:
            logger.warning("Failed to get belt position: %s", exc)
            position_data = None
            provider_connected = False

        # If provider failed entirely, return degraded result
        if position_data is None:
            logger.warning("Belt position provider returned no data; returning degraded localization")
            return {
                "belt_id": "unknown",
                "splice_id": splice_id,
                "position": 0.0,
                "position_confidence": 0.0,
                "is_estimated": True,
                "direction": "unknown",
                "speed": 0.0,
                "nearest_splice_id": None,
                "nearest_splice_distance": None,
                "timestamp": now.isoformat(),
            }

        # Extract fields with safe defaults
        belt_id = position_data.get("belt_id", "unknown")
        position = position_data.get("position", 0.0)
        is_estimated = position_data.get("is_estimated", True)
        direction = position_data.get("direction", "unknown")
        speed = position_data.get("speed", 0.0)
        nearest_splice_id = position_data.get("nearest_splice_id")
        nearest_splice_distance = position_data.get("nearest_splice_distance")
        raw_timestamp = position_data.get("timestamp", time.time())

        # -- Calculate position confidence --
        confidence = 1.0

        # Penalty if provider is not connected
        if not provider_connected:
            confidence -= 0.5

        # Penalty if position is estimated (not measured)
        if is_estimated:
            confidence -= 0.3

        # Penalty for inconsistency with recent history
        if self.position_history:
            last_entry = self.position_history[-1]
            last_position = last_entry.get("position", 0.0)
            last_timestamp = last_entry.get("raw_timestamp", raw_timestamp)
            last_speed = last_entry.get("speed", 0.0)

            time_delta = raw_timestamp - last_timestamp
            if time_delta > 0:
                position_delta = abs(position - last_position)
                # Maximum plausible distance: use the larger of current or last speed,
                # plus a generous tolerance factor of 2x for acceleration / measurement jitter
                max_speed = max(speed, last_speed, 0.1)
                max_plausible_distance = max_speed * time_delta * 2.0

                if position_delta > max_plausible_distance and max_plausible_distance > 0:
                    confidence -= 0.2
                    logger.debug(
                        "Position inconsistency detected: delta=%.2f m in %.2f s "
                        "(max plausible=%.2f m). Reducing confidence.",
                        position_delta, time_delta, max_plausible_distance,
                    )

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        # Store in position history
        history_entry = {
            "belt_id": belt_id,
            "position": position,
            "speed": speed,
            "direction": direction,
            "is_estimated": is_estimated,
            "raw_timestamp": raw_timestamp,
            "timestamp": now.isoformat(),
            "confidence": confidence,
        }
        self.position_history.append(history_entry)
        if len(self.position_history) > self.max_history:
            self.position_history = self.position_history[-self.max_history:]

        # Use splice_id from event_data if provided, otherwise fall back to nearest splice
        effective_splice_id = splice_id if splice_id != "unknown" else (nearest_splice_id or "unknown")

        result = {
            "belt_id": belt_id,
            "splice_id": effective_splice_id,
            "position": position,
            "position_confidence": round(confidence, 3),
            "is_estimated": is_estimated,
            "direction": direction,
            "speed": speed,
            "nearest_splice_id": nearest_splice_id,
            "nearest_splice_distance": nearest_splice_distance,
            "timestamp": now.isoformat(),
        }

        logger.debug(
            "Localized event for splice %s: position=%.2f m on %s (confidence=%.2f)",
            effective_splice_id, position, belt_id, confidence,
        )

        return result

    def get_position_history(self) -> list:
        """Return recent position history as list of dicts."""
        return list(self.position_history)

    def clear_history(self):
        """Clear position history."""
        self.position_history.clear()
