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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_active_slot(status: dict[str, Any]) -> int | None:
    # Common key variants seen in CFS/AMS-like telemetry payloads.
    for key in (
        "active_slot",
        "active_cfs_slot",
        "cfs_active_slot",
        "current_slot",
        "active_tray",
        "tray_now",
        "current_tray",
        "active_box_slot",
    ):
        slot = _parse_slot_number(status.get(key))
        if slot:
            return slot
    return None


def _extract_slots(status: dict[str, Any]) -> dict[int, dict[str, Any]]:
    slots: dict[int, dict[str, Any]] = {}

    # Pattern 1: explicit slots map/list already present.
    raw_slots = status.get("slots")
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

    # Pattern 2: per-slot objects keyed as slot_1 / cfs_slot_1 / ams_slot_1 etc.
    for key, value in status.items():
        if not isinstance(value, dict):
            continue
        lowered = str(key).lower()
        if "slot" not in lowered:
            continue
        # pick first number in the key as slot id
        digits = "".join(ch if ch.isdigit() else " " for ch in lowered).split()
        slot_no = _parse_slot_number(digits[0]) if digits else None
        if slot_no:
            slots.setdefault(slot_no, value)

    # Pattern 3: tray lists/maps used by some Moonraker profiles.
    for tray_key in ("trays", "tray", "filaments", "filament_slots"):
        raw_trays = status.get(tray_key)
        if isinstance(raw_trays, list):
            for idx, item in enumerate(raw_trays, start=1):
                slot_no = _parse_slot_number(item.get("slot")) if isinstance(item, dict) else None
                if not slot_no:
                    slot_no = idx if idx in (1, 2, 3, 4) else None
                if slot_no and isinstance(item, dict):
                    slots.setdefault(slot_no, item)
        elif isinstance(raw_trays, dict):
            for k, item in raw_trays.items():
                slot_no = _parse_slot_number(k)
                if slot_no and isinstance(item, dict):
                    slots.setdefault(slot_no, item)

    # Pattern 4: nested dict payloads (e.g. `filament_rack`, `box`).
    for value in status.values():
        if not isinstance(value, dict):
            continue
        nested = _extract_slots(value)
        for slot_no, payload in nested.items():
            slots.setdefault(slot_no, payload)

    return slots


def _is_cfs_candidate(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in (
            "cfs",
            "ams",
            "filament_rack",
            "filamentrack",
            "filament_box",
            "box",
        )
    )


def _extract_climate(status: dict[str, Any]) -> dict[str, float | None]:
    temp_keys = ("temperature", "temp", "cfs_temp", "chamber_temp")
    humidity_keys = ("humidity", "humid", "rh", "cfs_humidity")

    def _pick_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            if key in payload:
                parsed = _to_float(payload.get(key))
                if parsed is not None:
                    return parsed
        return None

    temperature_c = _pick_float(status, temp_keys)
    humidity_percent = _pick_float(status, humidity_keys)

    if temperature_c is None or humidity_percent is None:
        for value in status.values():
            if not isinstance(value, dict):
                continue
            if temperature_c is None:
                temperature_c = _pick_float(value, temp_keys)
            if humidity_percent is None:
                humidity_percent = _pick_float(value, humidity_keys)
            if temperature_c is not None and humidity_percent is not None:
                break

    return {
        "temperature_c": temperature_c,
        "humidity_percent": humidity_percent,
    }


async def _fetch_from_moonraker() -> dict[str, Any]:
    base = settings.moonraker_url.rstrip("/")
    if not base:
        return {
            "reachable": False,
            "source": "moonraker",
            "active_slot": None,
            "slots": {},
            "degraded_reason": "moonraker_url_missing",
        }

    list_url = f"{base}/printer/objects/list"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            listed = await client.get(list_url)
            listed.raise_for_status()
            objects = listed.json().get("result", {}).get("objects", [])
            if not isinstance(objects, list):
                objects = []

            candidates = [name for name in objects if isinstance(name, str) and _is_cfs_candidate(name)]
            if not candidates:
                return {
                    "reachable": False,
                    "source": "moonraker",
                    "active_slot": None,
                    "slots": {},
                    "degraded_reason": "moonraker_no_cfs_objects",
                }

            query = "&".join(candidates)
            query_url = f"{base}/printer/objects/query?{query}"
            response = await client.get(query_url)
            response.raise_for_status()
            status = response.json().get("result", {}).get("status", {})
            if not isinstance(status, dict):
                status = {}

            active_slot = _extract_active_slot(status)
            slots = _extract_slots(status)
            climate = _extract_climate(status)

            # If active slot not directly exposed, infer from strongest signal.
            if not active_slot:
                for slot_no, slot_payload in slots.items():
                    if not isinstance(slot_payload, dict):
                        continue
                    for marker in ("is_active", "active", "selected"):
                        if bool(slot_payload.get(marker)):
                            active_slot = slot_no
                            break
                    if active_slot:
                        break

            # Keep only lightweight useful fields when present.
            normalized: dict[int, dict[str, Any]] = {}
            for slot_no in (1, 2, 3, 4):
                raw = slots.get(slot_no, {})
                if not isinstance(raw, dict):
                    raw = {}
                remain_len = _to_float(raw.get("remain_len"))
                remain_weight = _to_float(raw.get("remain_weight"))
                normalized[slot_no] = {
                    "slot": slot_no,
                    "remain_len": remain_len,
                    "remain_weight": remain_weight,
                    "raw": raw,
                }

            return {
                "reachable": True,
                "source": "moonraker",
                "active_slot": active_slot,
                "slots": normalized,
                "climate": climate,
                "degraded_reason": "",
            }
    except Exception as exc:
        logger.warning("CFS moonraker fallback unreachable: %s", exc)
        return {
            "reachable": False,
            "source": "moonraker",
            "active_slot": None,
            "slots": {},
            "climate": {"temperature_c": None, "humidity_percent": None},
            "degraded_reason": str(exc),
        }


async def fetch_cfs_agent_state() -> dict[str, Any]:
    if not settings.cfs_agent_url:
        return await _fetch_from_moonraker()

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
                "climate": {
                    "temperature_c": _to_float(payload.get("temperature_c")),
                    "humidity_percent": _to_float(payload.get("humidity_percent")),
                },
                "degraded_reason": "",
            }
    except Exception as exc:
        logger.warning("CFS agent unreachable: %s", exc)
        return {
            "reachable": False,
            "source": "agent",
            "active_slot": None,
            "slots": {},
            "climate": {"temperature_c": None, "humidity_percent": None},
            "degraded_reason": str(exc),
        }
