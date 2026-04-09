"""Smoke tests for public API routes."""

import os
from pathlib import Path
from tempfile import gettempdir

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{Path(gettempdir()) / 'cfsspoolsync_test.db'}"
os.environ["DISABLE_MOONRAKER_POLLING"] = "1"

from app.main import app
from app.database import SessionLocal
from app.models import PrintJob
from app.routers import ocr as ocr_router


client = TestClient(app)


def test_printer_status_route_returns_shape() -> None:
    """Validate stable response keys for printer status endpoint.

    Returns:
    --------
        None:
            Asserts response schema compatibility.
    """
    response = client.get("/api/printer/status")
    assert response.status_code == 200

    payload = response.json()
    for key in [
        "reachable",
        "state",
        "filename",
        "progress",
        "extruder_temp",
        "extruder_target",
        "bed_temp",
        "bed_target",
        "cfs_temp",
        "cfs_humidity",
    ]:
        assert key in payload


def test_spool_crud_flow() -> None:
    """Cover basic spool create-read-update-delete flow.

    Returns:
    --------
        None:
            Asserts API behavior and backward-compatible keys.
    """
    create_payload = {
        "material": "PLA",
        "initial_weight": 1000,
    }
    created = client.post("/api/spools", json=create_payload)
    assert created.status_code == 201

    created_payload = created.json()
    assert "id" in created_payload
    spool_id = created_payload["id"]

    listed = client.get("/api/spools")
    assert listed.status_code == 200
    assert any(item["id"] == spool_id for item in listed.json())

    updated = client.put(f"/api/spools/{spool_id}", json={"brand": "eSUN"})
    assert updated.status_code == 200
    assert updated.json()["brand"] == "eSUN"

    deleted = client.delete(f"/api/spools/{spool_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}


def test_create_spool_from_cfs_source_assigns_active_slot() -> None:
    """Ensure create endpoint can persist active spool with CFS slot.

    Returns:
    --------
        None:
            Asserts status/cfs_slot assignment for CFS-sourced spool creation.
    """
    response = client.post(
        "/api/spools",
        json={
            "material": "PETG",
            "initial_weight": 1000,
            "status": "aktiv",
            "cfs_slot": 2,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "aktiv"
    assert payload["cfs_slot"] == 2


def test_create_spool_rejects_occupied_active_slot() -> None:
    """Prevent creating two active spools in the same CFS slot.

    Returns:
    --------
        None:
            Asserts conflict response on occupied CFS slot.
    """
    first = client.post(
        "/api/spools",
        json={
            "material": "PLA",
            "initial_weight": 1000,
            "status": "aktiv",
            "cfs_slot": 3,
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/spools",
        json={
            "material": "ABS",
            "initial_weight": 1000,
            "status": "aktiv",
            "cfs_slot": 3,
        },
    )
    assert second.status_code == 409


def test_cfs_route_shape() -> None:
    """Validate stable CFS overview payload shape.

    Returns:
    --------
        None:
            Asserts slot count and key names.
    """
    response = client.get("/api/cfs")
    assert response.status_code == 200

    payload = response.json()
    assert "slots" in payload
    assert len(payload["slots"]) == 4
    for slot in payload["slots"]:
        assert set(slot.keys()) == {"slot", "key", "spool"}


def test_scan_label_v2_response_contains_meta(monkeypatch) -> None:
    """Validate OCR v2 endpoint returns expected fields and metadata.

    Returns:
    --------
        None:
            Asserts expanded response shape for scan label endpoint.
    """
    client.post(
        "/api/spools",
        json={"material": "PLA", "brand": "Bambu Lab", "color": "#FFFFFF", "initial_weight": 1000},
    )

    monkeypatch.setattr(
        ocr_router,
        "run_ocr_v2",
        lambda *_args, **_kwargs: {
            "engine": "tesseract",
            "duration_ms": 180,
            "raw_text": "GEEETECH PETG 1.75mm Color: White Net Weight: 1KG",
            "warnings": [],
            "fields": {
                "brand": "Geeetech",
                "material": "PETG",
                "color_name": "White",
                "color_hex": "#FFFFFF",
                "diameter_mm": 1.75,
                "weight_g": 1000,
                "nozzle_min": 220,
                "nozzle_max": 250,
                "bed_min": 60,
                "bed_max": 85,
            },
            "field_meta": {
                "brand": {"confidence": 0.98, "status": "accepted", "source_lines": [], "accepted_value": "Geeetech", "candidates": ["Geeetech"]},
                "material": {"confidence": 0.98, "status": "accepted", "source_lines": [], "accepted_value": "PETG", "candidates": ["PETG"]},
            },
            "fallback_recommended": False,
            "suggestions": {"brand": ["Geeetech"], "material": ["PETG"], "color_name": ["White"]},
            "timing": {"total_ms": 180, "partial_timeout": False, "stages": {}},
        },
    )
    response = client.post(
        "/api/ocr/v2/scan",
        files={"file": ("label.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    for key in ["engine", "duration_ms", "fields", "field_meta", "warnings", "raw_text", "timing", "fallback_recommended", "suggestions"]:
        assert key in payload
    assert isinstance(payload["fields"], dict)
    assert isinstance(payload["field_meta"], dict)
    assert isinstance(payload["warnings"], list)
    assert payload["engine"] == "tesseract"
    assert payload["fields"]["brand"] == "Geeetech"
    assert payload["fields"]["material"] == "PETG"
    assert payload["field_meta"]["brand"]["status"] == "accepted"


def test_jobs_route_returns_only_one_running_job() -> None:
    """Ensure jobs API suppresses duplicate running jobs in list output.

    Returns:
    --------
        None:
            Asserts only one running job is returned.
    """
    db = SessionLocal()
    try:
        db.add(PrintJob(filename="same_file.gcode", status="running"))
        db.add(PrintJob(filename="same_file.gcode", status="running"))
        db.commit()
    finally:
        db.close()

    response = client.get("/api/jobs?limit=30")
    assert response.status_code == 200
    payload = response.json()
    running = [job for job in payload if job.get("status") == "running"]
    assert len(running) <= 1
