"""Async event bus for inter-module communication."""

import asyncio
import enum
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(str, enum.Enum):
    """All event types supported by the event bus."""
    SENSOR_UPDATE = "SENSOR_UPDATE"
    CAMERA_UPDATE = "CAMERA_UPDATE"
    INSPECTION_STARTED = "INSPECTION_STARTED"
    INSPECTION_COMPLETED = "INSPECTION_COMPLETED"
    DEFECT_DETECTED = "DEFECT_DETECTED"
    FUSION_UPDATED = "FUSION_UPDATED"
    CONDITION_UPDATED = "CONDITION_UPDATED"
    RISK_UPDATED = "RISK_UPDATED"
    ALERT_CREATED = "ALERT_CREATED"
    HARDWARE_STATUS = "HARDWARE_STATUS"
    SYSTEM_STATUS = "SYSTEM_STATUS"


# Type alias for event handler coroutines
EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class Event:
    """An event envelope carrying a type, payload, and metadata."""

    __slots__ = ("event_type", "payload", "timestamp", "source")

    def __init__(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        source: Optional[str] = None,
    ):
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.utcnow()
        self.source = source or "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


class EventBus:
    """Async publish/subscribe event bus.

    Subscribers register coroutine handlers for specific event types.
    Publishing an event dispatches it to all registered handlers concurrently.
    """

    _instance: Optional["EventBus"] = None

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[EventHandler]] = {
            et: [] for et in EventType
        }
        self._history: List[Event] = []
        self._max_history: int = 1000
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Return the global singleton event bus."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for tests)."""
        cls._instance = None

    async def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        async with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(
                    "Handler %s subscribed to %s", handler.__qualname__, event_type.value
                )

    async def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler for a specific event type."""
        async with self._lock:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(
                    "Handler %s unsubscribed from %s",
                    handler.__qualname__,
                    event_type.value,
                )
            except ValueError:
                logger.warning(
                    "Handler %s was not subscribed to %s",
                    handler.__qualname__,
                    event_type.value,
                )

    async def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        source: Optional[str] = None,
    ) -> None:
        """Publish an event to all subscribers of its type.

        Handlers are executed concurrently via asyncio.gather.  If any
        handler raises, the error is logged but other handlers still run.
        """
        event = Event(event_type=event_type, payload=payload, source=source)

        # Store in history ring buffer
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = list(self._subscribers[event_type])
        if not handlers:
            return

        logger.debug(
            "Publishing %s to %d handler(s)", event_type.value, len(handlers)
        )

        results = await asyncio.gather(
            *(self._safe_call(handler, event.to_dict()) for handler in handlers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Handler %s raised %s for event %s: %s",
                    handlers[i].__qualname__,
                    type(result).__name__,
                    event_type.value,
                    result,
                )

    @staticmethod
    async def _safe_call(handler: EventHandler, data: Dict[str, Any]) -> None:
        """Invoke a handler, letting exceptions propagate to gather."""
        await handler(data)

    def get_recent_events(self, limit: int = 50, event_type: Optional[EventType] = None) -> List[Dict[str, Any]]:
        """Return recent events, optionally filtered by type."""
        events = self._history
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        """Return the number of subscribers, optionally for a specific type."""
        if event_type is not None:
            return len(self._subscribers[event_type])
        return sum(len(handlers) for handlers in self._subscribers.values())
