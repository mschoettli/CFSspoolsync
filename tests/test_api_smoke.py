"""Smoke tests for public API routes."""

import os
from pathlib import Path
from tempfile import gettempdir

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{Path(gettempdir()) / 'cfsspoolsync_test.db'}"
os.environ["DISABLE_MOONRAKER_POLLING"] = "1"

from app.main import app
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


def test_scan_label_response_contains_meta(monkeypatch) -> None:
    """Validate OCR endpoint returns compatibility fields plus metadata.

    Returns:
    --------
        None:
            Asserts expanded response shape for scan label endpoint.
    """
    monkeypatch.setattr(
        ocr_router,
        "ocr_image",
        lambda _: "SUNLU PLA+ Color: White Printing Temp: 200-220C Net Weight: 1KG 1.75mm",
    )
    response = client.post(
        "/api/scan-label",
        files={"file": ("label.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    for key in ["material", "weight_g", "field_meta", "warnings", "raw_text"]:
        assert key in payload
    assert isinstance(payload["field_meta"], dict)
    assert isinstance(payload["warnings"], list)
