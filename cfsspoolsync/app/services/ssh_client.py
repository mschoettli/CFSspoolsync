import os
import json
import math
import logging
from typing import Optional, Dict, Any

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
SLOT_TO_ID  = {1: "A",   2: "B",   3: "C",   4: "D"}


def _get_client() -> paramiko.SSHClient:
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


def read_cfs_json() -> Optional[Dict[str, Any]]:
    try:
        client = _get_client()
        _, stdout, stderr = client.exec_command(f"cat '{CFS_JSON_PATH}'", timeout=10)
        raw = stdout.read().decode("utf-8").strip()
        err = stderr.read().decode("utf-8").strip()
        client.close()
        if err:
            logger.warning(f"SSH stderr: {err}")
        if not raw:
            logger.error("CFS JSON leer oder nicht gefunden")
            return None
        return json.loads(raw)
    except paramiko.AuthenticationException:
        logger.error("SSH Authentifizierung fehlgeschlagen")
        return None
    except Exception as exc:
        logger.error(f"SSH Lesefehler: {exc}")
        return None


def _parse_color(raw) -> str:
    """K2 uses a 7-char format with leading 0: #0FFFFFF → #FFFFFF"""
    if not raw:
        return "#888888"
    s = str(raw).strip().lstrip("#")
    if len(s) == 7 and s[0] == "0":
        s = s[1:]
    if len(s) == 6:
        try:
            int(s, 16)
            return f"#{s.upper()}"
        except ValueError:
            pass
    return "#888888"


def meters_to_grams(meters: float, diameter_mm: float, density: float) -> float:
    if meters <= 0 or diameter_mm <= 0 or density <= 0:
        return 0.0
    radius_cm = (diameter_mm / 2.0) / 10.0
    length_cm = meters * 100.0
    return math.pi * radius_cm ** 2 * length_cm * density


def _get_slot_list(data: Dict[str, Any]) -> list:
    """Real K2 structure: Material → info[0] → list → [{materialId: A/B/C/D, ...}]"""
    try:
        return data["Material"]["info"][0]["list"]
    except (KeyError, IndexError, TypeError):
        logger.error("CFS JSON Struktur unbekannt – 'Material.info[0].list' nicht gefunden")
        return []


def parse_slot(data: Dict[str, Any], slot_num: int) -> Optional[Dict]:
    entries = _get_slot_list(data)
    if not entries:
        return None

    target_id = SLOT_TO_ID.get(slot_num)
    entry = next((e for e in entries if e.get("materialId") == target_id), None)
    if entry is None:
        return None

    material   = entry.get("materialType", "").strip()
    remain_len = float(entry.get("remainLen", 0) or 0)
    diameter   = float(entry.get("diameter", 1.75) or 1.75)
    density    = float(entry.get("density", 1.24) or 1.24)

    return {
        "slot":            slot_num,
        "key":             SLOT_TO_KEY[slot_num],
        "material":        material,
        "color":           _parse_color(entry.get("color", "")),
        "brand":           entry.get("brand", "").strip(),
        "name":            entry.get("name", "").strip(),
        "nozzle_min":      int(entry.get("minTemp", 190) or 190),
        "nozzle_max":      int(entry.get("maxTemp", 230) or 230),
        "remain_len":      remain_len,
        "diameter":        diameter,
        "density":         density,
        "remaining_grams": round(meters_to_grams(remain_len, diameter, density), 1),
        "serial_num":      entry.get("serialNum", "").strip(),
        "loaded":          bool(material),
    }


def get_all_slots() -> Dict[int, Optional[Dict]]:
    data = read_cfs_json()
    if data is None:
        return {i: None for i in range(1, 5)}
    return {i: parse_slot(data, i) for i in range(1, 5)}


def get_slot(slot_num: int) -> Optional[Dict]:
    data = read_cfs_json()
    if data is None:
        return None
    return parse_slot(data, slot_num)
