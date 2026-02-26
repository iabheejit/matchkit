"""WebSocket connection manager for real-time chat."""
import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage active WebSocket connections per chat room.

    Tracks which connections belong to which rooms and organizations,
    enabling targeted message delivery and presence awareness.
    """

    def __init__(self):
        # room_id -> set of (websocket, org_id) tuples
        self._rooms: Dict[int, Set[tuple]] = {}
        # org_id -> set of room_ids they're connected to
        self._org_rooms: Dict[int, Set[int]] = {}

    async def connect(self, websocket: WebSocket, room_id: int, org_id: int):
        """Accept a WebSocket connection and register it to a room."""
        await websocket.accept()
        if room_id not in self._rooms:
            self._rooms[room_id] = set()
        self._rooms[room_id].add((websocket, org_id))

        if org_id not in self._org_rooms:
            self._org_rooms[org_id] = set()
        self._org_rooms[org_id].add(room_id)

        logger.info(f"WebSocket connected: org={org_id} room={room_id}")

    def disconnect(self, websocket: WebSocket, room_id: int, org_id: int):
        """Remove a WebSocket connection from a room."""
        if room_id in self._rooms:
            self._rooms[room_id].discard((websocket, org_id))
            if not self._rooms[room_id]:
                del self._rooms[room_id]

        if org_id in self._org_rooms:
            self._org_rooms[org_id].discard(room_id)
            if not self._org_rooms[org_id]:
                del self._org_rooms[org_id]

        logger.info(f"WebSocket disconnected: org={org_id} room={room_id}")

    async def broadcast_to_room(self, room_id: int, message: dict, exclude_org: int = None):
        """Send a message to all connections in a room, optionally excluding the sender."""
        if room_id not in self._rooms:
            return

        disconnected = []
        for ws, org_id in self._rooms[room_id]:
            if exclude_org and org_id == exclude_org:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append((ws, org_id))

        # Clean up broken connections
        for item in disconnected:
            self._rooms[room_id].discard(item)

    async def send_to_org(self, room_id: int, org_id: int, message: dict):
        """Send a message to a specific organization in a room."""
        if room_id not in self._rooms:
            return
        for ws, oid in self._rooms[room_id]:
            if oid == org_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    def get_room_presence(self, room_id: int) -> List[int]:
        """Get list of org_ids currently connected to a room."""
        if room_id not in self._rooms:
            return []
        return list({org_id for _, org_id in self._rooms[room_id]})

    def is_online(self, org_id: int) -> bool:
        """Check if an organization has any active connections."""
        return org_id in self._org_rooms and len(self._org_rooms[org_id]) > 0


# Singleton
connection_manager = ConnectionManager()
