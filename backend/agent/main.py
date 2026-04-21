"""Moonraker extension agent for CFSspoolsync."""
from __future__ import annotations

import asyncio
import json
import logging
from itertools import count
from typing import Any

import httpx
import websockets
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [cfs-agent] %(message)s",
)
logger = logging.getLogger("cfs-agent")


class Settings(BaseSettings):
    """Runtime settings for the Moonraker extension agent."""

    moonraker_ws_url: str = "ws://127.0.0.1:7125/websocket"
    moonraker_api_key: str = ""
    cfs_backend_url: str = "http://backend:8000"
    cfs_request_timeout: float = 10.0

    cfs_agent_name: str = "cfssync"
    cfs_agent_version: str = "1.0.0"
    cfs_agent_url: str = "https://github.com/mschoettli/CFSspoolsync"
    cfs_event_name: str = "cfssync.state_updated"
    cfs_poll_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class BackendBridge:
    """Bridge extension requests to the existing CFS backend REST API."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def call(self, method: str, args: Any) -> Any:
        """Dispatch an extension method to its corresponding backend endpoint."""
        if method == "cfssync.slots.list":
            return await self._request("GET", "/api/slots")
        if method == "cfssync.slot.assign":
            params = self._args_to_dict(args)
            slot_id = int(params["slot_id"])
            spool_id = int(params["spool_id"])
            return await self._request(
                "POST",
                f"/api/slots/{slot_id}/assign",
                json_payload={"spool_id": spool_id},
            )
        if method == "cfssync.slot.unassign":
            params = self._args_to_dict(args)
            slot_id = int(params["slot_id"])
            return await self._request("POST", f"/api/slots/{slot_id}/unassign")
        if method == "cfssync.spools.list":
            return await self._request("GET", "/api/spools")
        if method == "cfssync.spools.create":
            payload = self._args_to_dict(args)
            return await self._request("POST", "/api/spools", json_payload=payload)
        if method == "cfssync.spools.update":
            params = self._args_to_dict(args)
            spool_id = int(params.pop("spool_id"))
            return await self._request("PATCH", f"/api/spools/{spool_id}", json_payload=params)
        if method == "cfssync.spools.delete":
            params = self._args_to_dict(args)
            spool_id = int(params["spool_id"])
            return await self._request("DELETE", f"/api/spools/{spool_id}")
        if method == "cfssync.history.query":
            params = self._args_to_dict(args)
            query: dict[str, Any] = {"days": int(params.get("days", 7))}
            if "slot_id" in params and params["slot_id"] is not None:
                query["slot_id"] = int(params["slot_id"])
            return await self._request("GET", "/api/history", params=query)
        if method == "cfssync.settings.get":
            return await self._request("GET", "/api/settings")
        if method == "cfssync.settings.set":
            params = self._args_to_dict(args)
            allowed = {k: v for k, v in params.items() if k in {"language", "theme"}}
            return await self._request("PUT", "/api/settings", json_payload=allowed)
        raise ValueError(f"Unsupported method: {method}")

    async def snapshot(self) -> dict[str, Any]:
        """Return the current CFS/slot snapshot for event publication."""
        cfs_task = self._request("GET", "/api/cfs")
        slots_task = self._request("GET", "/api/slots")
        cfs, slots = await asyncio.gather(cfs_task, slots_task)
        return {"cfs": cfs, "slots": slots}

    async def _request(
        self,
        http_method: str,
        path: str,
        *,
        json_payload: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an HTTP request against the CFS backend and return JSON/null."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(http_method, url, json=json_payload, params=params)
        if response.status_code >= 400:
            detail = response.text.strip()
            raise RuntimeError(f"Backend error {response.status_code}: {detail}")
        if response.status_code == 204:
            return {"ok": True}
        return response.json()

    @staticmethod
    def _args_to_dict(args: Any) -> dict[str, Any]:
        """Normalize extension arguments to a dictionary."""
        if args is None:
            return {}
        if isinstance(args, dict):
            return args
        if isinstance(args, list):
            return {"args": args}
        raise ValueError("Arguments must be null, object, or array")


class MoonrakerAgent:
    """Persistent Moonraker WebSocket client exposing CFS extension methods."""

    def __init__(self, settings: Settings, backend: BackendBridge) -> None:
        self.settings = settings
        self.backend = backend
        self._request_id = count(1)
        self._last_snapshot_hash: str | None = None

    async def run_forever(self) -> None:
        """Reconnect loop for the agent lifetime."""
        while True:
            try:
                await self._run_connection()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent disconnected, retrying: %s", exc)
                await asyncio.sleep(3.0)

    async def _run_connection(self) -> None:
        """Open websocket, identify as agent, and handle extension traffic."""
        logger.info("Connecting to Moonraker: %s", self.settings.moonraker_ws_url)
        async with websockets.connect(self.settings.moonraker_ws_url, ping_interval=20, ping_timeout=20) as ws:
            await self._rpc_call(
                ws,
                "server.connection.identify",
                {
                    "client_name": self.settings.cfs_agent_name,
                    "version": self.settings.cfs_agent_version,
                    "type": "agent",
                    "url": self.settings.cfs_agent_url,
                    "api_key": self.settings.moonraker_api_key or None,
                },
            )
            try:
                await self._rpc_call(
                    ws,
                    "connection.register_remote_method",
                    {"method_name": "cfssync_refresh"},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Remote method registration not available on this Moonraker: %s",
                    exc,
                )
            logger.info("Identified as agent '%s'", self.settings.cfs_agent_name)

            await self._publish_snapshot(ws, force=True)
            next_publish = asyncio.get_running_loop().time() + self.settings.cfs_poll_seconds

            while True:
                timeout = max(0.1, next_publish - asyncio.get_running_loop().time())
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    await self._handle_message(ws, raw)
                except asyncio.TimeoutError:
                    pass

                now = asyncio.get_running_loop().time()
                if now >= next_publish:
                    await self._publish_snapshot(ws, force=False)
                    next_publish = now + self.settings.cfs_poll_seconds

    async def _rpc_call(self, ws: Any, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC request and wait for its response ID."""
        req_id = next(self._request_id)
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}
        await ws.send(json.dumps(payload))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(f"Moonraker RPC error for {method}: {msg['error']}")
                return msg.get("result")
            await self._handle_parsed_message(ws, msg)

    async def _handle_message(self, ws: Any, raw: str) -> None:
        """Parse a websocket frame and dispatch it."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Skipping non-JSON payload from Moonraker")
            return
        await self._handle_parsed_message(ws, msg)

    async def _handle_parsed_message(self, ws: Any, msg: dict[str, Any]) -> None:
        """Handle incoming method calls destined for the agent."""
        method = msg.get("method")
        if not method:
            return

        req_id = msg.get("id")
        params = msg.get("params")

        if method == "cfssync_refresh":
            await self._publish_snapshot(ws, force=True)
            if req_id is not None:
                await self._send_result(ws, req_id, {"ok": True})
            return

        if not method.startswith("cfssync."):
            return

        try:
            result = await self.backend.call(method, params)
            if req_id is not None:
                await self._send_result(ws, req_id, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Method %s failed: %s", method, exc)
            if req_id is not None:
                await self._send_error(ws, req_id, -32000, str(exc))

    async def _publish_snapshot(self, ws: Any, *, force: bool) -> None:
        """Publish a state-changed event when CFS/slot data changes."""
        snapshot = await self.backend.snapshot()
        serialized = json.dumps(snapshot, sort_keys=True, default=str)
        if not force and serialized == self._last_snapshot_hash:
            return

        self._last_snapshot_hash = serialized
        event_payload = {
            "jsonrpc": "2.0",
            "method": "connection.send_event",
            "params": {
                "event": self.settings.cfs_event_name,
                "data": snapshot,
            },
        }
        await ws.send(json.dumps(event_payload))

    @staticmethod
    async def _send_result(ws: Any, req_id: int, result: Any) -> None:
        """Send JSON-RPC success response for agent method calls."""
        payload = {"jsonrpc": "2.0", "id": req_id, "result": result}
        await ws.send(json.dumps(payload))

    @staticmethod
    async def _send_error(ws: Any, req_id: int, code: int, message: str) -> None:
        """Send JSON-RPC error response for agent method calls."""
        payload = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
        await ws.send(json.dumps(payload))


async def main() -> None:
    """Create agent dependencies and start the reconnect loop."""
    settings = Settings()
    backend = BackendBridge(settings.cfs_backend_url, settings.cfs_request_timeout)
    logger.info("Starting cfs-moonraker-agent (%s)", settings.cfs_agent_version)
    agent = MoonrakerAgent(settings, backend)
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
