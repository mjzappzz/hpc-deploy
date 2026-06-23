"""
In-memory WebSocket connection manager for task log broadcasting.

Single-process only. No Redis/Celery.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TaskLogWebSocketManager:
    """Manages WebSocket connections per task_id for live log streaming."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, task_id: str, ws: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await ws.accept()
        if task_id not in self._connections:
            self._connections[task_id] = set()
        self._connections[task_id].add(ws)
        logger.debug("[ws] client connected to task %s (total: %d)", task_id, len(self._connections[task_id]))

    def disconnect(self, task_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        conns = self._connections.get(task_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._connections[task_id]
        logger.debug("[ws] client disconnected from task %s", task_id)

    async def send_json(self, task_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all clients subscribed to a task."""
        conns = self._connections.get(task_id)
        if not conns:
            return

        payload = json.dumps(message, ensure_ascii=False, default=str)
        stale: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        # Clean up failed connections
        for ws in stale:
            self.disconnect(task_id, ws)

    async def broadcast_log(
        self,
        task_id: str,
        level: str,
        message: str,
        created_at: str | None = None,
    ) -> None:
        """Broadcast a log line to all subscribers."""
        msg: dict[str, Any] = {
            "type": "log",
            "task_id": task_id,
            "level": level,
            "line": message,
        }
        if created_at:
            msg["created_at"] = created_at
        await self.send_json(task_id, msg)

    async def broadcast_status(self, task_id: str, status: str) -> None:
        """Broadcast a status change to all subscribers."""
        await self.send_json(task_id, {
            "type": "status",
            "task_id": task_id,
            "status": status,
        })

    async def broadcast_done(self, task_id: str, status: str) -> None:
        """Broadcast task completion to all subscribers."""
        await self.send_json(task_id, {
            "type": "done",
            "task_id": task_id,
            "status": status,
        })

    def count_connections(self, task_id: str) -> int:
        """Return number of active connections for a task."""
        return len(self._connections.get(task_id, set()))

    # ── Sync-friendly helpers (for use from sync task runner code) ──

    def broadcast_log_sync(
        self,
        task_id: str,
        level: str,
        message: str,
        created_at: str | None = None,
    ) -> None:
        """Synchronous version of broadcast_log — fires async task.

        Never raises. Failures are silently logged.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast_log(task_id, level, message, created_at))
            else:
                logger.debug("[ws] no running loop, skipping broadcast for %s", task_id)
        except RuntimeError:
            logger.debug("[ws] no event loop, skipping broadcast for %s", task_id)

    def broadcast_status_sync(self, task_id: str, status: str) -> None:
        """Synchronous version of broadcast_status."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast_status(task_id, status))
        except RuntimeError:
            pass

    def broadcast_done_sync(self, task_id: str, status: str) -> None:
        """Synchronous version of broadcast_done."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast_done(task_id, status))
        except RuntimeError:
            pass


# Singleton instance
ws_manager = TaskLogWebSocketManager()
