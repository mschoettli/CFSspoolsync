"""SSH client utilities for reading CFS slot information from K2."""

import json
import logging
import math
import os
from typing import Any, Optional

import paramiko

logger = logging.getLogger(__name__)

K2_HOST = os.getenv("K2_HOST", "192.168.178.192")
K2_SSH_USER = os.getenv("K2_SSH_USER", "root")
K2_SSH_KEY = os.getenv("K2_SSH_KEY", "/root/.ssh/id_k2")
CFS_JSON_PATH = os.getenv(
    "CFS_JSON_PATH",
    "/mnt/UDISK/creality/userdata/box/material_box_info.json",
)

SLOT_TO_KEY = {1: "Spule 1", 2: "Spule 2", 3: "Spule 3", 4: "Spule 4"}
SLOT_TO_ID = {1: "A", 2: "B", 3: "C", 4: "D"}


def _get_client() -> paramiko.SSHClient:
    """Create an SSH client connected to the configured K2 host."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=K2_HOST,
        username=K2_SSH_USER,
        key_filename=K2_SSH_KEY,
        timeout=8,
        banner_timeout=8,
    )
    return client


def read_cfs_json() -> Optional[dict[str, Any]]:
    """Read and parse the raw CFS JSON file from the printer."""
    try:
        client = _get_client()
        _, stdout, stderr = client.exec_command(f"cat '{CFS_JSON_PATH}'", timeout=10)
        raw = stdout.read().decode("utf-8").strip()
        err = stderr.read().decode("utf-8").strip()
        client.close()

        if err:
            logger.warning("SSH stderr: %s", err)
        if not raw:
            logger.error("CFS JSON empty or not found")
            return None
        return json.loads(raw)
    except paramiko.AuthenticationException:
        logger.error("SSH authentication failed")
        return None
    except Exception as exc:
        logger.error("SSH read error: %s", exc)
        return None


def _parse_color(raw: Any) -> str:
    """Normalize K2 color format values to canonical #RRGGBB."""
    if not raw:
        return "#888888"

    value = str(raw).strip().lstrip("#")
    if len(value) == 7 and value[0] == "0":
        value = value[1:]

    if len(value) == 6:
        try:
            int(value, 16)
            return f"#{value.upper()}"
        except ValueError:
            pass

    return "#888888"


def meters_to_grams(meters: float, diameter_mm: float, density: float) -> float:
    """Convert filament length to grams based on diameter and density."""
    if meters <= 0 or diameter_mm <= 0 or density <= 0:
        return 0.0

    radius_cm = (diameter_mm / 2.0) / 10.0
    length_cm = meters * 100.0
    return math.pi * radius_cm**2 * length_cm * density


def _get_slot_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the slot list from the known K2 JSON structure."""
    try:
        return data["Material"]["info"][0]["list"]
    except (KeyError, IndexError, TypeError):
        logger.error("CFS JSON structure invalid, expected Material.info[0].list")
        return []


def parse_slot(data: dict[str, Any], slot_num: int) -> Optional[dict[str, Any]]:
    """Parse one slot from the CFS JSON payload."""
    entries = _get_slot_list(data)
    if not entries:
        return None

    target_id = SLOT_TO_ID.get(slot_num)
    entry = next((item for item in entries if item.get("materialId") == target_id), None)
    if entry is None:
        return None

    material = entry.get("materialType", "").strip()
    remain_len = float(entry.get("remainLen", 0) or 0)
    diameter = float(entry.get("diameter", 1.75) or 1.75)
    density = float(entry.get("density", 1.24) or 1.24)

    return {
        "slot": slot_num,
        "key": SLOT_TO_KEY[slot_num],
        "material": material,
        "color": _parse_color(entry.get("color", "")),
        "brand": entry.get("brand", "").strip(),
        "name": entry.get("name", "").strip(),
        "nozzle_min": int(entry.get("minTemp", 190) or 190),
        "nozzle_max": int(entry.get("maxTemp", 230) or 230),
        "remain_len": remain_len,
        "diameter": diameter,
        "density": density,
        "remaining_grams": round(meters_to_grams(remain_len, diameter, density), 1),
        "serial_num": entry.get("serialNum", "").strip(),
        "loaded": bool(material),
    }


def get_all_slots() -> dict[int, Optional[dict[str, Any]]]:
    """Return parsed data for all known CFS slots."""
    data = read_cfs_json()
    if data is None:
        return {i: None for i in range(1, 5)}
    return {i: parse_slot(data, i) for i in range(1, 5)}


def get_slot(slot_num: int) -> Optional[dict[str, Any]]:
    """Return parsed data for one CFS slot."""
    data = read_cfs_json()
    if data is None:
        return None
    return parse_slot(data, slot_num)
