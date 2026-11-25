"""WebSocket manager for real-time data streaming."""
import asyncio
import json
import logging
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from gpuguard.utils.logging import get_logger

logger = get_logger("api.websocket")


@dataclass
class ClientInfo:
    """Connected WebSocket client info."""
    client_id: str
    connected_at: datetime
    subscriptions: Set[str]
    last_ping: datetime


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        self._clients: Dict[str, WebSocket] = {}
        self._client_info: Dict[str, ClientInfo] = {}
        self._subscriptions: Dict[str, Set[str]] = {}  # topic -> set of client_ids
        self._lock = asyncio.Lock()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._clients[client_id] = websocket
            self._client_info[client_id] = ClientInfo(
                client_id=client_id,
                connected_at=datetime.utcnow(),
                subscriptions=set(),
                last_ping=datetime.utcnow(),
            )
        logger.info(f"Client connected: {client_id} (total: {len(self._clients)})")

        # Start broadcast task if not running
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def disconnect(self, client_id: str) -> None:
        """Disconnect a client."""
        async with self._lock:
            self._clients.pop(client_id, None)
            info = self._client_info.pop(client_id, None)
            if info:
                for topic in info.subscriptions:
                    self._subscriptions.get(topic, set()).discard(client_id)
        logger.info(f"Client disconnected: {client_id} (total: {len(self._clients)})")

    async def subscribe(self, client_id: str, topics: List[str]) -> None:
        """Subscribe client to topics."""
        async with self._lock:
            if client_id not in self._client_info:
                return
            info = self._client_info[client_id]
            for topic in topics:
                info.subscriptions.add(topic)
                if topic not in self._subscriptions:
                    self._subscriptions[topic] = set()
                self._subscriptions[topic].add(client_id)
        logger.debug(f"Client {client_id} subscribed to: {topics}")

    async def unsubscribe(self, client_id: str, topics: List[str]) -> None:
        """Unsubscribe client from topics."""
        async with self._lock:
            if client_id not in self._client_info:
                return
            info = self._client_info[client_id]
            for topic in topics:
                info.subscriptions.discard(topic)
                self._subscriptions.get(topic, set()).discard(client_id)

    async def send_personal_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific client."""
        async with self._lock:
            websocket = self._clients.get(client_id)
            if not websocket:
                return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)
            return False

    async def broadcast(self, topic: str, message: Dict[str, Any]) -> int:
        """Broadcast message to all subscribers of a topic."""
        async with self._lock:
            client_ids = self._subscriptions.get(topic, set()).copy()

        sent = 0
        for client_id in client_ids:
            if await self.send_personal_message(client_id, message):
                sent += 1
        return sent

    async def broadcast_all(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all connected clients."""
        async with self._lock:
            client_ids = list(self._clients.keys())

        sent = 0
        for client_id in client_ids:
            if await self.send_personal_message(client_id, message):
                sent += 1
        return sent

    async def _broadcast_loop(self) -> None:
        """Background task to process message queue."""
        while True:
            try:
                # Wait for messages with timeout
                topic, message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                await self.broadcast(topic, message)
            except asyncio.TimeoutError:
                # Check if any clients remain
                async with self._lock:
                    if not self._clients:
                        break
                continue
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")

    async def queue_broadcast(self, topic: str, message: Dict[str, Any]) -> None:
        """Queue a message for broadcast."""
        await self._message_queue.put((topic, message))

    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """Get list of connected clients."""
        return [
            {
                "client_id": info.client_id,
                "connected_at": info.connected_at.isoformat(),
                "subscriptions": list(info.subscriptions),
                "last_ping": info.last_ping.isoformat(),
            }
            for info in self._client_info.values()
        ]

    async def handle_ping(self, client_id: str) -> None:
        """Handle ping from client."""
        async with self._lock:
            if client_id in self._client_info:
                self._client_info[client_id].last_ping = datetime.utcnow()

    async def close_all(self) -> None:
        """Close all connections."""
        async with self._lock:
            for client_id, websocket in self._clients.items():
                try:
                    await websocket.close()
                except Exception:
                    pass
            self._clients.clear()
            self._client_info.clear()
            self._subscriptions.clear()

        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass


# Global instance
_ws_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get global WebSocket manager instance."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager