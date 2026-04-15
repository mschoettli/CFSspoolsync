"""Tests for centralized remaining-weight update behavior."""

import os
from pathlib import Path
from tempfile import gettempdir

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{Path(gettempdir()) / 'cfsspoolsync_test.db'}"
os.environ["DISABLE_MOONRAKER_POLLING"] = "1"

from app.main import app
from app.database import SessionLocal
from app.models import Spool
from app.routers import cfs as cfs_router
from app.services import remaining_weight_service
from app.services.ssh_client import meters_to_grams

client = TestClient(app)


def test_apply_from_k2_remain_len_uses_calibration_factor(monkeypatch) -> None:
    """Apply K2 remainLen with calibration and verify effective grams."""
    db = SessionLocal()
    try:
        spool = Spool(
            material="PETG",
            color="#FFFFFF",
            brand="Generic",
            name="PETG",
            nozzle_min=220,
            nozzle_max=270,
            bed_temp=60,
            initial_weight=1000.0,
            remaining_weight=400.0,
            status="aktiv",
            cfs_slot=1,
            diameter=1.75,
            density=1.24,
            calibration_factor=2.0,
        )
        db.add(spool)
        db.commit()
        db.refresh(spool)

        monkeypatch.setattr(remaining_weight_service, "CFS_REMAINLEN_MULTIPLIER", 1.0)
        result = remaining_weight_service.apply_from_k2_remain_len(
            spool=spool,
            remain_len=20.0,
            source=remaining_weight_service.SOURCE_K2_LIVE_SYNC,
            now=spool.updated_at,
        )

        expected_raw = round(meters_to_grams(20.0, 1.75, 1.24), 1)
        assert result.raw_k2_g == expected_raw
        assert result.new_weight == round(expected_raw * 2.0, 1)
        assert result.applied_factor == 2.0
        assert spool.last_weight_source == remaining_weight_service.SOURCE_K2_LIVE_SYNC
    finally:
        db.close()


def test_apply_manual_measurement_respects_threshold(monkeypatch) -> None:
    """Keep remaining unchanged for tiny deltas below configured threshold."""
    db = SessionLocal()
    try:
        spool = Spool(
            material="PLA",
            color="#FFFFFF",
            brand="Test",
            name="PLA",
            nozzle_min=190,
            nozzle_max=240,
            bed_temp=60,
            initial_weight=1000.0,
            remaining_weight=500.0,
            status="lager",
            diameter=1.75,
            density=1.24,
        )
        db.add(spool)
        db.commit()
        db.refresh(spool)

        monkeypatch.setattr(remaining_weight_service, "REMAINING_WEIGHT_CHANGE_THRESHOLD_G", 0.5)
        result = remaining_weight_service.apply_manual_measurement(
            spool=spool,
            measured_weight_g=500.3,
            source=remaining_weight_service.SOURCE_MANUAL_CALIBRATION,
            now=spool.updated_at,
        )
        assert result.changed is False
        assert spool.remaining_weight == 500.0
    finally:
        db.close()


def test_cfs_sync_returns_extended_weight_diagnostics(monkeypatch) -> None:
    """Expose additive diagnostics in sync response without breaking fields."""
    db = SessionLocal()
    try:
        spool = Spool(
            material="PETG",
            color="#FFFFFF",
            brand="Generic",
            name="PETG",
            nozzle_min=220,
            nozzle_max=270,
            bed_temp=60,
            initial_weight=1000.0,
            remaining_weight=100.0,
            status="aktiv",
            cfs_slot=1,
            serial_num="ABC",
            diameter=1.75,
            density=1.24,
            calibration_factor=1.5,
        )
        db.add(spool)
        db.commit()
        db.refresh(spool)
    finally:
        db.close()

    monkeypatch.setattr(
        cfs_router.ssh_client,
        "get_all_slots",
        lambda: {
            1: {
                "slot": 1,
                "key": "Spule 1",
                "material": "PETG",
                "brand": "Generic",
                "name": "PETG",
                "color": "#FFFFFF",
                "nozzle_min": 220,
                "nozzle_max": 270,
                "remain_len": 12.0,
                "diameter": 1.75,
                "density": 1.24,
                "remaining_grams": 0.0,
                "serial_num": "ABC",
                "loaded": True,
            },
            2: {"slot": 2, "key": "Spule 2", "loaded": False},
            3: {"slot": 3, "key": "Spule 3", "loaded": False},
            4: {"slot": 4, "key": "Spule 4", "loaded": False},
        },
    )

    response = client.post("/api/cfs/sync")
    assert response.status_code == 200
    payload = response.json()
    assert "synced" in payload
    assert "updates" in payload
    assert payload["updates"]
    first = payload["updates"][0]
    for key in (
        "raw_remain_len",
        "normalized_remain_len",
        "raw_k2_g",
        "effective_g",
        "applied_factor",
        "source",
    ):
        assert key in first
    assert first["source"] == "k2_live_sync"
