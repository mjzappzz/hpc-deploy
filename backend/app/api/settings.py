import logging
import subprocess
from pathlib import Path

from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.config import BACKEND_ROOT
from app.db.database import get_db
from app.models.settings import SystemSetting
from app.schemas.settings import (
    DEFAULT_SETTINGS,
    FORBIDDEN_KEYS,
    SettingsResponse,
    SettingsUpdate,
)
from app.schemas.ssh_key import SSHKeyGenerateResponse
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
    _: str = Depends(require_admin_token),
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
        actor="admin",
        message=f"updated keys: {', '.join(update_data.keys())}" if update_data else "no changes",
        detail={"updated_keys": list(update_data.keys())},
    )

    # Return full merged state
    merged = _get_settings_dict(db)
    return _db_to_response(merged)


@router.post("/ssh-key/generate-default", response_model=SSHKeyGenerateResponse)
def generate_default_ssh_key(
    _: str = Depends(require_admin_token),
) -> SSHKeyGenerateResponse:
    """Generate default id_ed25519 / id_ed25519.pub in backend/keys/."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key = KEYS_DIR / "id_ed25519"
    public_key = KEYS_DIR / "id_ed25519.pub"

    if private_key.is_file() or public_key.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="默认密钥已存在，如需重新生成请手动删除现有密钥文件",
        )

    if not _ssh_keygen_available():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ssh-keygen 不可用，请安装 openssh-client",
        )

    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(private_key),
                "-N", "",
                "-C", "hpcdeploy-default",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密钥生成失败: {exc.stderr or exc.stdout or str(exc)}",
        ) from exc

    # Set permissions
    try:
        private_key.chmod(0o600)
        if public_key.is_file():
            public_key.chmod(0o644)
    except OSError:
        pass  # non-fatal

    return SSHKeyGenerateResponse(
        private_key="id_ed25519",
        public_key="id_ed25519.pub",
        message="默认密钥生成成功",
    )


def _ssh_keygen_available() -> bool:
    try:
        result = subprocess.run(
            ["ssh-keygen", "--help"],
            capture_output=True,
            text=True,
        )
        return result.returncode in (0, 1)
    except FileNotFoundError:
        return False
