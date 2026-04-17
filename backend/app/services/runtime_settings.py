from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return default
    return str(row.value or "")


def set_setting(db: Session, key: str, value: Any) -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    normalized = "" if value is None else str(value)
    if row:
        row.value = normalized
    else:
        row = AppSetting(key=key, value=normalized)
        db.add(row)
    db.commit()
    db.refresh(row)
    return str(row.value or "")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
