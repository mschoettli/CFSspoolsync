"""Centralized remaining-weight update logic for active spools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from typing import Optional

from app.models import Spool
from app.services.ssh_client import meters_to_grams

REMAINING_WEIGHT_CHANGE_THRESHOLD_G = float(
    os.getenv("REMAINING_WEIGHT_CHANGE_THRESHOLD_G", "0.1")
)
CFS_REMAINLEN_MULTIPLIER = float(os.getenv("CFS_REMAINLEN_MULTIPLIER", "1.0"))

SOURCE_K2_LIVE_SYNC = "k2_live_sync"
SOURCE_PRINT_END = "print_end_snapshot"
SOURCE_MANUAL_CALIBRATION = "manual_calibration"


@dataclass(slots=True)
class RemainingWeightUpdate:
    """Result payload for one remaining-weight write attempt."""

    changed: bool
    old_weight: float
    new_weight: float
    raw_remain_len: Optional[float]
    normalized_remain_len: Optional[float]
    raw_k2_g: Optional[float]
    effective_g: float
    applied_factor: Optional[float]
    source: str


def _normalize_source(source: str) -> str:
    """Normalize source labels for diagnostics.

    Args:
    -----
        source (str):
            Source tag from caller.

    Returns:
    --------
        str:
            Normalized source label.
    """
    value = str(source or "").strip().lower()
    if value in {SOURCE_K2_LIVE_SYNC, SOURCE_PRINT_END, SOURCE_MANUAL_CALIBRATION}:
        return value
    return SOURCE_K2_LIVE_SYNC


def _clamp_weight(weight_g: float, initial_weight_g: float) -> float:
    """Clamp a weight value to valid spool bounds.

    Args:
    -----
        weight_g (float):
            Candidate weight in grams.
        initial_weight_g (float):
            Spool reference start weight.

    Returns:
    --------
        float:
            Bounded weight value.
    """
    return max(0.0, min(float(weight_g), float(initial_weight_g)))


def apply_from_k2_remain_len(
    spool: Spool,
    remain_len: float,
    source: str,
    now: datetime,
) -> RemainingWeightUpdate:
    """Apply one remain-length measurement to a spool.

    Args:
    -----
        spool (Spool):
            Target spool entity.
        remain_len (float):
            Raw remain-length from K2 JSON.
        source (str):
            Update source label.
        now (datetime):
            Timestamp used for spool mutation.

    Returns:
    --------
        RemainingWeightUpdate:
            Update diagnostics and effective written value.
    """
    raw_remain_len = max(0.0, float(remain_len or 0.0))
    normalized_remain_len = raw_remain_len * CFS_REMAINLEN_MULTIPLIER
    raw_k2_g = round(
        meters_to_grams(
            normalized_remain_len,
            float(spool.diameter or 0.0),
            float(spool.density or 0.0),
        ),
        1,
    )

    applied_factor = (
        float(spool.calibration_factor)
        if spool.calibration_factor is not None
        else None
    )
    effective = raw_k2_g if applied_factor is None else round(raw_k2_g * applied_factor, 1)
    effective = round(_clamp_weight(effective, float(spool.initial_weight or 0.0)), 1)

    old_weight = float(spool.remaining_weight or 0.0)
    changed = abs(old_weight - effective) >= REMAINING_WEIGHT_CHANGE_THRESHOLD_G
    if changed:
        spool.remaining_weight = effective

    spool.last_raw_remain_len = round(raw_remain_len, 3)
    spool.last_normalized_remain_len = round(normalized_remain_len, 3)
    spool.last_raw_k2_g = raw_k2_g
    spool.last_weight_source = _normalize_source(source)
    spool.last_weight_updated_at = now
    spool.updated_at = now

    return RemainingWeightUpdate(
        changed=changed,
        old_weight=round(old_weight, 1),
        new_weight=effective,
        raw_remain_len=round(raw_remain_len, 3),
        normalized_remain_len=round(normalized_remain_len, 3),
        raw_k2_g=raw_k2_g,
        effective_g=effective,
        applied_factor=applied_factor,
        source=_normalize_source(source),
    )


def apply_manual_measurement(
    spool: Spool,
    measured_weight_g: float,
    source: str,
    now: datetime,
    calibration_factor: Optional[float] = None,
    raw_k2_g: Optional[float] = None,
) -> RemainingWeightUpdate:
    """Apply one direct measured weight to a spool.

    Args:
    -----
        spool (Spool):
            Target spool entity.
        measured_weight_g (float):
            Net measured weight in grams.
        source (str):
            Update source label.
        now (datetime):
            Timestamp used for spool mutation.
        calibration_factor (Optional[float]):
            Optional new calibration factor.
        raw_k2_g (Optional[float]):
            Optional raw K2 grams measured at calibration time.

    Returns:
    --------
        RemainingWeightUpdate:
            Update diagnostics and effective written value.
    """
    effective = round(
        _clamp_weight(float(measured_weight_g or 0.0), float(spool.initial_weight or 0.0)),
        1,
    )
    old_weight = float(spool.remaining_weight or 0.0)
    changed = abs(old_weight - effective) >= REMAINING_WEIGHT_CHANGE_THRESHOLD_G
    if changed:
        spool.remaining_weight = effective

    if calibration_factor is not None:
        spool.calibration_factor = round(float(calibration_factor), 4)
    if raw_k2_g is not None:
        spool.last_raw_k2_g = round(float(raw_k2_g), 1)
    spool.last_weight_source = _normalize_source(source)
    spool.last_weight_updated_at = now
    spool.updated_at = now

    return RemainingWeightUpdate(
        changed=changed,
        old_weight=round(old_weight, 1),
        new_weight=effective,
        raw_remain_len=spool.last_raw_remain_len,
        normalized_remain_len=spool.last_normalized_remain_len,
        raw_k2_g=round(float(raw_k2_g), 1) if raw_k2_g is not None else spool.last_raw_k2_g,
        effective_g=effective,
        applied_factor=spool.calibration_factor,
        source=_normalize_source(source),
    )
