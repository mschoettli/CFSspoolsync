import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_slot_number(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        slot = int(value)
        return slot if slot in (1, 2, 3, 4) else None
    text = str(value).strip().upper()
    if text in {"A", "B", "C", "D"}:
        return {"A": 1, "B": 2, "C": 3, "D": 4}[text]
    try:
        slot = int(text)
        return slot if slot in (1, 2, 3, 4) else None
    except ValueError:
        return None


async def fetch_cfs_agent_state() -> dict[str, Any]:
    if not settings.cfs_agent_url:
        return {
            "reachable": False,
            "source": "agent",
            "active_slot": None,
            "slots": {},
            "degraded_reason": "agent_url_missing",
        }

    headers = {}
    if settings.cfs_agent_token:
        headers["Authorization"] = f"Bearer {settings.cfs_agent_token}"

    url = f"{settings.cfs_agent_url.rstrip('/')}/api/cfs/state"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            raw_slots = payload.get("slots", {}) if isinstance(payload, dict) else {}
            slots: dict[int, dict[str, Any]] = {}
            if isinstance(raw_slots, list):
                for item in raw_slots:
                    if not isinstance(item, dict):
                        continue
                    slot_no = _parse_slot_number(item.get("slot"))
                    if slot_no:
                        slots[slot_no] = item
            elif isinstance(raw_slots, dict):
                for k, item in raw_slots.items():
                    slot_no = _parse_slot_number(k)
                    if slot_no and isinstance(item, dict):
                        slots[slot_no] = item

            return {
                "reachable": True,
                "source": "agent",
                "active_slot": _parse_slot_number(payload.get("active_slot")),
                "slots": slots,
                "degraded_reason": "",
            }
    except Exception as exc:
        logger.warning("CFS agent unreachable: %s", exc)
        return {
            "reachable": False,
            "source": "agent",
            "active_slot": None,
            "slots": {},
            "degraded_reason": str(exc),
        }
