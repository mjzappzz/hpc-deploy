import logging
from pathlib import Path

from app.core.audit import write_audit_log
from app.core.config import BACKEND_ROOT
from app.db.database import get_db
from app.models.settings import SystemSetting
from app.schemas.settings import (
    DEFAULT_SETTINGS,
    FORBIDDEN_KEYS,
    SettingsResponse,
    SettingsUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

KEYS_DIR = BACKEND_ROOT / "keys"


def _get_settings_dict(db: Session) -> dict[str, str]:
    """Merge DB-stored settings with defaults. DB values take precedence."""
    rows = db.query(SystemSetting).all()
    stored = {row.key: row.value for row in rows}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(stored)
    return merged


def _db_to_response(merged: dict[str, str]) -> SettingsResponse:
    """Convert internal dict to SettingsResponse, with type coercion.

    remote_task_root and remote_apptainer_dir are fixed values — ignore DB.
    """
    return SettingsResponse(
        default_ssh_key_name=merged.get("default_ssh_key_name", ""),
        remote_task_root="$HOME/hpcdeploy/tasks",
        remote_apptainer_dir="$HOME/hpcdeploy/apptainer",
        ssh_key_dir="backend/keys",
        ssh_key_dir_absolute=str(KEYS_DIR.resolve()),
    )


def _validate_ssh_key_name(key_name: str) -> None:
    """Validate that key_name exists in backend/keys/."""
    if not key_name:
        return  # empty is allowed (no default key)
    key_path = KEYS_DIR / key_name
    if not key_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSH key file not found: {key_name}",
        )


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    """Return all system settings (DB values + defaults)."""
    merged = _get_settings_dict(db)
    return _db_to_response(merged)


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Update system settings. Only allowed keys are accepted."""
    update_data = payload.model_dump(exclude_none=True)

    # Reject any forbidden keys explicitly
    for key in update_data:
        if key in FORBIDDEN_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"field not allowed: {key}",
            )

    # Validate default_ssh_key_name exists
    if "default_ssh_key_name" in update_data:
        _validate_ssh_key_name(update_data["default_ssh_key_name"])

    # Save each key to DB
    for key, raw_value in update_data.items():
        str_value = str(raw_value)
        setting = db.get(SystemSetting, key)
        if setting is None:
            setting = SystemSetting(key=key, value=str_value)
            db.add(setting)
        else:
            setting.value = str_value
        logger.info("[settings] updated %s = %s", key, str_value)

    db.commit()

    write_audit_log(
        db, action="settings.update", target_type="settings", status="success",
        message=f"updated keys: {', '.join(update_data.keys())}" if update_data else "no changes",
        detail={"updated_keys": list(update_data.keys())},
    )

    # Return full merged state
    merged = _get_settings_dict(db)
    return _db_to_response(merged)
