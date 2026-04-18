"""Einfacher WebSocket-Broadcast-Manager."""
import asyncio
import json
from typing import Set
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        data = json.dumps(payload, default=_default)
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self._conns)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.discard(ws)


def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Not serializable: {type(o)}")


manager = ConnectionManager()
