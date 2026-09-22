"""WebSocket manager and endpoint for live event streaming."""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import get_settings
from ..core.events import EventBus, EventType

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events to all clients."""

    _instance = None

    def __init__(self):
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._subscribed = False

    @classmethod
    def get_instance(cls) -> "ConnectionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

        if not self._subscribed:
            await self._subscribe_to_events()
            self._subscribed = True

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        if not self._connections:
            return

        data = json.dumps(message, default=str)
        dead: List[WebSocket] = []

        for ws in list(self._connections):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_personal(self, ws: WebSocket, message: Dict[str, Any]) -> None:
        """Send a message to a single client."""
        try:
            await ws.send_text(json.dumps(message, default=str))
        except Exception:
            await self.disconnect(ws)

    async def _subscribe_to_events(self) -> None:
        """Subscribe to all event bus events and forward them to clients."""
        bus = EventBus.get_instance()
        for event_type in EventType:
            await bus.subscribe(event_type, self._on_event)

    async def _on_event(self, event_data: Dict[str, Any]) -> None:
        """Handler called by the event bus for every event."""
        msg = {
            "type": event_data.get("event_type", "UNKNOWN"),
            "payload": event_data.get("payload", {}),
            "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
        }
        await self.broadcast(msg)

    async def start_heartbeat(self) -> None:
        """Start a background task that sends periodic heartbeats."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self) -> None:
        settings = get_settings()
        interval = settings.WS_HEARTBEAT
        while True:
            try:
                await asyncio.sleep(interval)
                await self.broadcast({
                    "type": "heartbeat",
                    "payload": {
                        "server_time": datetime.utcnow().isoformat(),
                        "connections": len(self._connections),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """Main WebSocket endpoint for live event streaming."""
    manager = ConnectionManager.get_instance()
    await manager.connect(ws)

    try:
        # Send welcome message
        await manager.send_personal(ws, {
            "type": "connected",
            "payload": {
                "message": "Connected to SpliceTracker live feed",
                "server_time": datetime.utcnow().isoformat(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            # Wait for client messages (ping/pong, control messages)
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await manager.send_personal(ws, {
                        "type": "pong",
                        "payload": {"server_time": datetime.utcnow().isoformat()},
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                elif msg_type == "subscribe":
                    # Acknowledge subscription request
                    await manager.send_personal(ws, {
                        "type": "subscribed",
                        "payload": {"events": msg.get("payload", {}).get("events", [])},
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            except json.JSONDecodeError:
                await manager.send_personal(ws, {
                    "type": "error",
                    "payload": {"message": "Invalid JSON"},
                    "timestamp": datetime.utcnow().isoformat(),
                })

    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        await manager.disconnect(ws)
