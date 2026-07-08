import logging
import subprocess
from pathlib import Path

from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.config import BACKEND_ROOT
from app.db.database import get_db
from app.models.settings import SystemSetting
from app.core.auth import verify_admin_password
from app.schemas.settings import (
    DEFAULT_SETTINGS,
    FORBIDDEN_KEYS,
    ChangePasswordRequest,
    ChangePasswordResponse,
    SettingsResponse,
    SettingsUpdate,
)
from app.schemas.ssh_key import SSHKeyGenerateResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

KEYS_DIR = BACKEND_ROOT / "keys"
DB_PATH = BACKEND_ROOT / "data" / "hpc_control_panel.db"
ARTIFACTS_DIR = BACKEND_ROOT / "data" / "artifacts"
BACKUPS_DIR = BACKEND_ROOT / "data" / "backups"
APPTAINER_DIR = BACKEND_ROOT / "apptainer"
MPI_SCRIPTS_DIR = BACKEND_ROOT / "scripts" / "mpi"
STRESS_SCRIPTS_DIR = BACKEND_ROOT / "scripts" / "stress"


def _path_size(path: Path) -> tuple[int | None, int | None]:
    if not path.exists():
        return None, None
    if path.is_file():
        return path.stat().st_size, 1

    total = 0
    count = 0
    for item in path.rglob("*"):
        try:
            if item.is_symlink() or not item.is_file():
                continue
            total += item.stat().st_size
            count += 1
        except OSError:
            continue
    return total, count


def _runtime_path(
    *,
    key: str,
    label: str,
    path: Path | str,
    kind: str,
    description: str,
    attention: bool = False,
) -> dict[str, object]:
    if isinstance(path, Path):
        exists = path.exists()
        size_bytes, file_count = _path_size(path)
        display_path = path.as_posix()
    else:
        exists = False
        size_bytes = None
        file_count = None
        display_path = path

    return {
        "key": key,
        "label": label,
        "path": display_path,
        "kind": kind,
        "description": description,
        "exists": exists,
        "size_bytes": size_bytes,
        "file_count": file_count,
        "attention": attention,
    }


def _build_runtime_paths() -> list[dict[str, object]]:
    return [
        _runtime_path(
            key="database",
            label="SQLite 主数据库",
            path=DB_PATH,
            kind="file",
            description="服务器、任务、日志、系统设置、审计和报告摘要缓存都在这里。",
            attention=True,
        ),
        _runtime_path(
            key="task_logs",
            label="任务日志",
            path=DB_PATH,
            kind="database",
            description="任务日志记录在 SQLite 数据库内，不是独立日志文件。",
            attention=True,
        ),
        _runtime_path(
            key="ssh_keys",
            label="SSH 密钥目录",
            path=KEYS_DIR,
            kind="directory",
            description="用户放置或系统生成的 SSH 私钥/公钥。密钥不进入 Git。",
            attention=True,
        ),
        _runtime_path(
            key="mpi_scripts",
            label="服务器环境脚本库",
            path=MPI_SCRIPTS_DIR,
            kind="directory",
            description="服务器环境、安装、运维配置脚本，任务执行时按选择上传到远端。",
        ),
        _runtime_path(
            key="stress_scripts",
            label="服务器压测脚本库",
            path=STRESS_SCRIPTS_DIR,
            kind="directory",
            description="GPU、CPU/内存、磁盘服务器压测脚本，任务执行时按选择上传到远端。",
        ),
        _runtime_path(
            key="artifacts",
            label="远端回收结果",
            path=ARTIFACTS_DIR,
            kind="directory",
            description="远端拉回来的报告、日志、CSV、XLSX、JSON 等任务结果。",
            attention=True,
        ),
        _runtime_path(
            key="sqlite_backups",
            label="数据库备份目录",
            path=BACKUPS_DIR,
            kind="directory",
            description="scripts/backup_sqlite.sh 生成的 SQLite 备份文件。",
            attention=True,
        ),
        _runtime_path(
            key="apptainer",
            label="Apptainer 镜像目录",
            path=APPTAINER_DIR,
            kind="directory",
            description=".sif 镜像存放目录，镜像不进入 Git。",
            attention=True,
        ),
        _runtime_path(
            key="remote_tasks",
            label="远端任务工作目录",
            path="$HOME/hpcdeploy/tasks/<task_type>/<脚本名_时间>/",
            kind="remote",
            description="每台目标服务器执行任务时生成，包含 task.log、.hpcdeploy.pid、报告和临时文件。",
            attention=True,
        ),
        _runtime_path(
            key="remote_apptainer",
            label="远端 Apptainer 目录",
            path="$HOME/hpcdeploy/apptainer/",
            kind="remote",
            description="每台目标服务器上的 .sif 镜像分发目录。",
            attention=True,
        ),
    ]


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
        auto_cleanup_enabled=_str_to_bool(merged.get("auto_cleanup_enabled", "false")),
        local_artifact_retention_days=_str_to_int(merged.get("local_artifact_retention_days"), 30),
        auto_cleanup_time=merged.get("auto_cleanup_time", "03:00"),
        auto_cleanup_last_run_at=merged.get("auto_cleanup_last_run_at", ""),
        auto_cleanup_last_deleted_dirs=_str_to_int(merged.get("auto_cleanup_last_deleted_dirs"), 0),
        auto_cleanup_last_freed_bytes=_str_to_int(merged.get("auto_cleanup_last_freed_bytes"), 0),
        auto_cleanup_last_failed_count=_str_to_int(merged.get("auto_cleanup_last_failed_count"), 0),
        auto_cleanup_last_status=merged.get("auto_cleanup_last_status", ""),
        auto_cleanup_last_message=merged.get("auto_cleanup_last_message", ""),
        admin_password_configured=bool(merged.get("admin_password", "")),
        runtime_paths=_build_runtime_paths(),
    )


def _str_to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _str_to_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


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


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_admin_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> ChangePasswordResponse:
    """Change the admin password. Saves to DB; env var still works as fallback."""
    # Verify current password first
    if not verify_admin_password(payload.current_password, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前密码错误",
        )

    # Save new password to DB
    setting = db.get(SystemSetting, "admin_password")
    if setting is None:
        setting = SystemSetting(key="admin_password", value=payload.new_password)
        db.add(setting)
    else:
        setting.value = payload.new_password
    db.commit()

    write_audit_log(
        db, action="settings.change_password", target_type="settings", status="success",
        actor="admin",
        message="管理员密码已修改",
        detail={},
    )

    logger.info("[settings] admin password changed")
    return ChangePasswordResponse(success=True, message="管理员密码修改成功")


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
