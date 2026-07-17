import base64
import hashlib
import hmac
import json
import logging
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.config import BACKEND_ROOT, settings
from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.db.database import SessionLocal, get_db
from app.models.server import Server
from app.models.settings import SystemSetting
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.cleanup import (
    REMOTE_ALLOWED_TARGETS,
    REMOTE_TARGETS,
    ApptainerImageItem,
    ApptainerImageScanResult,
    AutoCleanupStatusResponse,
    DeleteResultItem,
    DatabaseTaskLogItem,
    DatabaseTaskLogsScanResult,
    LocalArtifactDirectory,
    LocalArtifactFile,
    LocalArtifactTaskItem,
    LocalArtifactsDeleteRequest,
    LocalArtifactsDeleteResponse,
    LocalArtifactsScanResult,
    RemoteDeleteRequest,
    RemoteDeleteResponse,
    RemoteDirectoryScan,
    RemoteDirInfo,
    RemoteScanAllResult,
    RemoteScanRequest,
    RemoteScanResult,
    RemoteServerScanResult,
    RemoteTaskDirDeleteRequest,
    RemoteTaskDirDeleteResponse,
    RemoteTaskDirInfo,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import LargeBinary, cast, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cleanup", tags=["cleanup"])

ARTIFACTS_ROOT = ARTIFACTS_DIR.resolve()

# ── Helpers ──


def _format_size_text(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    if bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


def _ensure_inside_root(resolved: Path, root: Path, path_label: str) -> None:
    """Security check: ensure resolved path stays inside the allowed root."""
    try:
        resolved.relative_to(root)
    except ValueError:
        logger.warning("[cleanup] path traversal blocked: %s -> %s", path_label, resolved)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path traversal blocked: {path_label}",
        )


def _resolve_artifact_path(relative: str) -> Path:
    """Resolve a relative path under ARTIFACTS_ROOT, with traversal protection."""
    if relative.startswith("/"):
        logger.warning("[cleanup] absolute path rejected: %s", relative)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="absolute path not allowed",
        )
    resolved = (ARTIFACTS_ROOT / relative).resolve()
    _ensure_inside_root(resolved, ARTIFACTS_ROOT, relative)
    return resolved


def _extract_task_id(relative: str) -> str | None:
    """Extract the first path segment as the task_id hint."""
    parts = relative.replace("\\", "/").strip("/").split("/")
    if parts and parts[0]:
        return parts[0]
    return None


def _hide_task_from_history_for_artifact_delete(db: Session, relative: str) -> None:
    task_id = _extract_task_id(relative)
    if not task_id:
        return
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        return
    task.hidden_from_history = 1
    task.hidden_reason = "local artifacts deleted from settings"
    task.hidden_at = datetime.utcnow()
    db.add(TaskLog(task_id=task.task_id, level="SYSTEM", message="task hidden from history after local artifacts deletion"))


def _target_label(key: str) -> str:
    labels = {
        "tasks": "任务工作目录",
        "downloads": "临时下载目录",
        "tmp": "临时目录",
    }
    return labels.get(key, key)


def _server_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        return {"key_path": None, "password": server.password}
    return {"key_path": server.key_path, "password": None}


def _server_auth_kwargs_raw(
    auth_type: str,
    password: str | None,
    key_path: str | None,
) -> dict[str, str | None]:
    if auth_type == "password":
        return {"key_path": None, "password": password}
    return {"key_path": key_path, "password": None}


def _strip_script_ext(name: str | None) -> str:
    if not name:
        return ""
    return Path(name).name.removesuffix(".sh").removesuffix(".py")


def _infer_date_label(*values: str | None) -> str:
    for value in values:
        if not value:
            continue
        match = re.search(r"(20\d{6})", value)
        if match:
            return match.group(1)
    return ""


def _sort_timestamp_from_remote_dir(item: RemoteTaskDirInfo) -> float:
    if item.modified_at:
        return item.modified_at.timestamp()
    date_label = item.date_label or _infer_date_label(item.dir_name)
    time_match = re.search(r"20\d{6}[-_]?(\d{6})", item.dir_name)
    if date_label:
        try:
            time_part = time_match.group(1) if time_match else "000000"
            return datetime.strptime(f"{date_label}{time_part}", "%Y%m%d%H%M%S").timestamp()
        except ValueError:
            return 0
    return 0


def _infer_task_type_label(*values: str | None) -> str:
    text = " ".join(v or "" for v in values).lower()
    if "cpu_mem" in text or "stress_cpu_mem" in text:
        return "CPU/内存"
    if "gpu_stress" in text or "gpu_report" in text or "gpu" in text:
        return "GPU"
    if "disk_stress" in text or "disk_report" in text or "fio" in text:
        return "磁盘"
    if "stress" in text:
        return "压测"
    return "任务"


def _long_task_type_label(label: str) -> str:
    return {
        "GPU": "GPU压测",
        "CPU/内存": "CPU/内存压测",
        "磁盘": "磁盘压测",
    }.get(label, label)


def _task_type_label_from_task(task: Task) -> str:
    script_label = _strip_script_ext(task.file_name)
    inferred = _infer_task_type_label(script_label)
    if inferred != "任务":
        return inferred
    return {
        "stress": "压测",
        "script": "脚本",
        "apptainer": "容器",
    }.get(task.task_type or "", task.task_type or "任务")


def _build_display_title(parts: list[str]) -> str:
    return " · ".join([p for p in parts if p])


def _build_task_display_metadata(
    task: Task | None,
    db: Session,
    *,
    dir_name: str,
    path: str,
    source: str,
    fallback_origin: str,
    file_names: list[str] | None = None,
) -> dict[str, Any]:
    file_names = file_names or []
    if task is not None:
        server_name = ""
        if task.server_id:
            server = db.query(Server).filter(Server.id == task.server_id).first()
            if server:
                server_name = server.name or ""
        script_label = _strip_script_ext(task.file_name)
        task_type_label = _task_type_label_from_task(task)
        display_type_label = _long_task_type_label(task_type_label)
        date_label = task.created_at.strftime("%Y%m%d") if task.created_at else _infer_date_label(task.task_id, dir_name)
        display_title = _build_display_title([server_name, display_type_label, script_label, date_label])
        return {
            "task_id": task.task_id,
            "display_title": display_title,
            "server_name": server_name,
            "task_type_label": task_type_label,
            "script_label": script_label,
            "date_label": date_label,
            "dir_name": dir_name,
            "path": path,
            "source": source,
            "found_in_db": True,
            "batch_id": task.batch_id,
            "inferred_batch_key": None,
            "is_batch_task": bool(task.batch_id),
            "task_source_label": "批次任务" if task.batch_id else "单次任务",
            "task_status": task.status or "",
            "sequence_index": task.sequence_index,
        }

    task_type_label = _infer_task_type_label(dir_name, *file_names)
    script_label = _infer_script_label(dir_name, file_names)
    date_label = _infer_date_label(dir_name, *file_names)
    display_parts = [fallback_origin, _long_task_type_label(task_type_label)]
    if source == "local_artifact" and script_label:
        display_parts.append(script_label)
    display_parts.append(date_label)
    return {
        "task_id": dir_name if dir_name.startswith("task-") else None,
        "display_title": _build_display_title(display_parts),
        "server_name": fallback_origin,
        "task_type_label": task_type_label,
        "script_label": script_label,
        "date_label": date_label,
        "dir_name": dir_name,
        "path": path,
        "source": source,
        "found_in_db": False,
        "batch_id": None,
        "inferred_batch_key": None,
        "is_batch_task": False,
        "task_source_label": "未匹配",
        "task_status": "",
        "sequence_index": None,
    }


def _infer_script_label(dir_name: str, file_names: list[str]) -> str:
    candidates = [dir_name, *file_names]
    text = " ".join(candidates).lower()
    if "cpu_mem_stress_report" in text:
        return "cpu_mem_stress_report"
    if "gpu_stress_report" in text:
        return "gpu_stress_report"
    if "disk_stress_report" in text:
        return "disk_stress_report"
    if "cpu_mem" in text:
        return "cpu_mem_stress_report"
    if "gpu" in text:
        return "gpu_stress_report"
    if "disk" in text or "fio" in text:
        return "disk_stress_report"
    return ""


def _script_name_for_remote_dir(dir_name: str) -> str:
    if dir_name.startswith("gpu_stress_"):
        return "gpu_stress_report.sh"
    if dir_name.startswith("cpu_mem_stress_"):
        return "cpu_mem_stress_report.sh"
    if dir_name.startswith("disk_stress_"):
        return "disk_stress_report.sh"
    return ""


def _task_id_batch_prefix(task_id: str | None) -> str | None:
    if not task_id:
        return None
    match = re.match(r"^(task-20\d{6}-\d{6})-", task_id)
    return match.group(1) if match else None


def _apply_inferred_batch_flags(directories: list[LocalArtifactDirectory]) -> None:
    groups: dict[str, list[LocalArtifactDirectory]] = {}
    for item in directories:
        if item.is_batch_task or not item.task_id:
            continue
        prefix = _task_id_batch_prefix(item.task_id)
        if prefix:
            groups.setdefault(prefix, []).append(item)

    required = {"GPU", "CPU/内存", "磁盘"}
    for prefix, items in groups.items():
        types = {item.task_type_label for item in items}
        if len(items) >= 3 and required.issubset(types):
            inferred_key = prefix.removeprefix("task-")
            for item in items:
                item.is_batch_task = True
                item.task_source_label = "疑似批次"
                item.inferred_batch_key = inferred_key


def _local_artifact_task_item(item: LocalArtifactDirectory) -> LocalArtifactTaskItem | None:
    if not item.task_id:
        return None
    return LocalArtifactTaskItem(
        task_id=item.task_id,
        task_display_name=item.task_display_name or item.display_title or item.name,
        display_title=item.display_title or item.task_display_name or item.name,
        server_name=item.server_name,
        task_type_label=item.task_type_label,
        script_label=item.script_label,
        date_label=item.date_label,
        status=item.task_status,
        sequence_index=item.sequence_index,
        relative_path=item.relative_path,
        file_count=item.file_count,
        size_bytes=item.size_bytes,
        size_text=item.size_text,
        modified_at=item.modified_at,
    )


def _group_local_artifact_batches(directories: list[LocalArtifactDirectory]) -> list[LocalArtifactDirectory]:
    grouped: dict[str, list[LocalArtifactDirectory]] = {}
    passthrough: list[LocalArtifactDirectory] = []

    for item in directories:
        if item.batch_id:
            grouped.setdefault(item.batch_id, []).append(item)
        else:
            task_item = _local_artifact_task_item(item)
            if task_item:
                item.child_tasks = [task_item]
                item.child_relative_paths = [item.relative_path]
            passthrough.append(item)

    for batch_id, items in grouped.items():
        items.sort(key=lambda item: (item.sequence_index if item.sequence_index is not None else 999, item.date_label, item.script_label, item.task_id or item.name))
        total_files = sum(item.file_count for item in items)
        total_size = sum(item.size_bytes for item in items)
        latest_mtime = max(
            (item.modified_at for item in items if item.modified_at is not None),
            default=None,
        )
        servers = sorted({item.server_name for item in items if item.server_name})
        scripts = [item.script_label for item in items if item.script_label]
        date_label = next((item.date_label for item in items if item.date_label), "")
        title = _build_display_title([
            "批次",
            "、".join(servers),
            "压测",
            "、".join(dict.fromkeys(scripts)),
            date_label,
        ])
        files: list[LocalArtifactFile] = []
        for item in items:
            files.extend(item.files)
        files.sort(key=lambda f: f.relative_path)

        child_tasks: list[LocalArtifactTaskItem] = []
        for item in items:
            task_item = _local_artifact_task_item(item)
            if task_item:
                child_tasks.append(task_item)

        passthrough.append(LocalArtifactDirectory(
            name=batch_id,
            relative_path=batch_id,
            type="batch",
            file_count=total_files,
            size_bytes=total_size,
            size_text=_format_size_text(total_size),
            modified_at=latest_mtime,
            task_id=None,
            task_display_name=title,
            display_title=title,
            server_name="、".join(servers),
            task_type_label="压测",
            script_label="、".join(dict.fromkeys(scripts)),
            date_label=date_label,
            dir_name=batch_id,
            path=batch_id,
            source="local_artifact_batch",
            found_in_db=any(item.found_in_db for item in items),
            batch_id=batch_id,
            inferred_batch_key=None,
            is_batch_task=True,
            task_source_label="批次任务",
            task_status="",
            sequence_index=None,
            child_relative_paths=[item.relative_path for item in items],
            child_tasks=child_tasks,
            files=files,
        ))

    return passthrough


def _normalize_remote_dir_path(path: str | None) -> str:
    if not path:
        return ""
    stripped = path.strip().rstrip("/")
    while "//" in stripped:
        stripped = stripped.replace("//", "/")
    return stripped


def _find_task_by_remote_dir(db: Session, remote_path: str, dir_name: str) -> Task | None:
    normalized_remote_path = _normalize_remote_dir_path(remote_path)
    task = db.query(Task).filter(Task.remote_work_dir == remote_path).first()
    if task is not None:
        return task
    for candidate in db.query(Task).filter(Task.remote_work_dir.isnot(None)).all():
        candidate_path = _normalize_remote_dir_path(candidate.remote_work_dir)
        if candidate_path == normalized_remote_path:
            return candidate
    like_suffix = f"%/{dir_name}"
    task = db.query(Task).filter(Task.remote_work_dir.like(like_suffix)).first()
    if task is not None:
        return task
    basename_matches = [
        candidate for candidate in db.query(Task).filter(Task.remote_work_dir.isnot(None)).all()
        if Path(_normalize_remote_dir_path(candidate.remote_work_dir)).name == dir_name
    ]
    if len(basename_matches) == 1:
        return basename_matches[0]

    script_name = _script_name_for_remote_dir(dir_name)
    date_label = _infer_date_label(dir_name)
    if not script_name or not date_label:
        return None

    start = datetime.strptime(date_label, "%Y%m%d")
    end = start + timedelta(days=1)
    candidates = (
        db.query(Task)
        .filter(Task.file_name == script_name)
        .filter(Task.created_at >= start)
        .filter(Task.created_at < end)
        .all()
    )
    return candidates[0] if len(candidates) == 1 else None


def _build_task_dir_delete_key(server_id: int, task_dir_path: str) -> str:
    payload = json.dumps(
        {"server_id": server_id, "path": task_dir_path},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse_task_dir_delete_key(delete_key: str, server_id: int) -> str:
    try:
        body, sig = delete_key.rsplit(".", 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid delete key")

    expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid delete key")

    padded = body + "=" * (-len(body) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid delete key") from exc

    if int(data.get("server_id", 0)) != server_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delete key server mismatch")
    task_dir_path = str(data.get("path") or "").strip()
    if not _is_safe_task_dir_path(task_dir_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsafe task directory path")
    return task_dir_path


# ───── Local artifacts scan (directory-aggregated) ─────


@router.get("/local-artifacts/scan", response_model=LocalArtifactsScanResult)
def scan_local_artifacts(db: Session = Depends(get_db)) -> LocalArtifactsScanResult:
    """
    Scan local artifacts directory.
    Returns directories grouped, with file details under each directory.
    """
    start = monotonic()
    logger.info("[cleanup] local-artifacts scan start root=%s", ARTIFACTS_ROOT)

    if not ARTIFACTS_ROOT.is_dir():
        return LocalArtifactsScanResult(
            root=str(ARTIFACTS_ROOT),
            total_dirs=0,
            total_files=0,
            total_size_bytes=0,
            items=[],
        )

    directories: list[LocalArtifactDirectory] = []
    total_files = 0
    total_size = 0

    # Gather first-level entries
    first_level: list[Path] = sorted(ARTIFACTS_ROOT.iterdir(), key=lambda p: p.name)

    for entry in first_level:
        if entry.is_dir():
            fc, sz = _build_directory_entry(entry, directories, db=db)
            total_files += fc
            total_size += sz
        # Files handled below as "未归档文件"

    # Gather root-level files -> "未归档文件" group
    root_files: list[LocalArtifactFile] = []
    root_size = 0
    root_latest_mtime: datetime | None = None

    for entry in first_level:
        if not entry.is_file():
            continue
        try:
            sz = entry.stat().st_size
            root_size += sz
            total_size += sz
            total_files += 1
            mtime = datetime.fromtimestamp(entry.stat().st_mtime) if entry.stat().st_mtime else None
            if mtime and (root_latest_mtime is None or mtime > root_latest_mtime):
                root_latest_mtime = mtime
            root_files.append(LocalArtifactFile(
                name=entry.name,
                relative_path=entry.name,
                size_bytes=sz,
                size_text=_format_size_text(sz),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    if root_files:
        directories.append(LocalArtifactDirectory(
            name="未归档文件",
            relative_path=".",
            file_count=len(root_files),
            size_bytes=root_size,
            size_text=_format_size_text(root_size),
            modified_at=root_latest_mtime,
            files=root_files,
        ))

    _apply_inferred_batch_flags(directories)
    directories = _group_local_artifact_batches(directories)

    # Sort local task result directories by modified time desc; keep root-level files last.
    directories.sort(
        key=lambda d: (
            1 if d.name == "未归档文件" else 0,
            -(d.modified_at.timestamp() if d.modified_at else 0),
            d.name,
        )
    )

    elapsed = monotonic() - start
    logger.info(
        "[cleanup] local-artifacts scan done dirs=%d files=%d size=%d elapsed=%.3fs",
        len(directories), total_files, total_size, elapsed,
    )
    return LocalArtifactsScanResult(
        root=str(ARTIFACTS_ROOT),
        total_dirs=len(directories),
        total_files=total_files,
        total_size_bytes=total_size,
        items=directories,
    )


@router.get("/local-logs/scan", response_model=DatabaseTaskLogsScanResult)
def scan_local_logs(
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> DatabaseTaskLogsScanResult:
    """List database-backed task logs with their UTF-8 message payload sizes."""
    logs = db.query(TaskLog).order_by(TaskLog.created_at.desc(), TaskLog.id.desc()).limit(limit).all()
    total_logs = db.query(TaskLog).count()
    total_message_bytes = int(
        db.query(func.coalesce(func.sum(func.length(cast(TaskLog.message, LargeBinary))), 0)).scalar() or 0
    )

    return DatabaseTaskLogsScanResult(
        total_logs=total_logs,
        total_message_bytes=total_message_bytes,
        returned_logs=len(logs),
        items=[
            DatabaseTaskLogItem(
                id=log.id,
                task_id=log.task_id,
                level=log.level,
                message=log.message,
                message_bytes=len((log.message or "").encode("utf-8")),
                created_at=log.created_at,
            )
            for log in logs
        ],
    )


@router.get("/auto-cleanup/status", response_model=AutoCleanupStatusResponse)
def get_auto_cleanup_status(db: Session = Depends(get_db)) -> AutoCleanupStatusResponse:
    settings_rows = db.query(SystemSetting).all()
    values = {row.key: row.value for row in settings_rows}
    return AutoCleanupStatusResponse(
        enabled=_str_to_bool(values.get("auto_cleanup_enabled", "false")),
        retention_days=_str_to_int(values.get("local_artifact_retention_days"), 30),
        cleanup_time=values.get("auto_cleanup_time", "03:00"),
        last_run_at=values.get("auto_cleanup_last_run_at", ""),
        last_deleted_dirs=_str_to_int(values.get("auto_cleanup_last_deleted_dirs"), 0),
        last_freed_bytes=_str_to_int(values.get("auto_cleanup_last_freed_bytes"), 0),
        last_failed_count=_str_to_int(values.get("auto_cleanup_last_failed_count"), 0),
        last_status=values.get("auto_cleanup_last_status", ""),
        last_message=values.get("auto_cleanup_last_message", ""),
    )


def _str_to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _str_to_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _build_task_display_name(task_id: str, db: Session) -> str | None:
    """Query task table and build a readable display name."""
    try:
        t = db.query(Task).filter(Task.task_id == task_id).first()
        if t is None:
            logger.warning("[cleanup] task_name: %s not found in DB", task_id)
            return None
        server_name = ""
        if t.server_id:
            svr = db.query(Server).filter(Server.id == t.server_id).first()
            if svr:
                server_name = svr.name or ""
        task_type_label = {
            "stress": "压测",
            "script": "脚本",
            "apptainer": "容器",
        }.get(t.task_type or "", t.task_type or "")
        script_name = (t.file_name or "").replace(".sh", "").replace(".py", "")
        date_str = ""
        if t.created_at:
            date_str = t.created_at.strftime("%Y%m%d")
        parts = [p for p in [server_name, task_type_label, script_name, date_str] if p]
        result = " · ".join(parts)
        logger.info("[cleanup] task_name: %s -> %s", task_id, result)
        return result
    except Exception as exc:
        logger.error("[cleanup] task_name error for %s: %s", task_id, exc)
        return None


def _build_directory_entry(
    entry: Path,
    directories: list[LocalArtifactDirectory],
    db: Session | None = None,
) -> tuple[int, int]:
    """Build a LocalArtifactDirectory from a first-level directory entry.
    Returns (file_count, size_bytes) for this directory.
    """
    dir_files: list[LocalArtifactFile] = []
    dir_size = 0
    dir_file_count = 0
    latest_mtime: datetime | None = None

    for f in sorted(entry.rglob("*")):
        if not f.is_file():
            continue
        try:
            sz = f.stat().st_size
            dir_size += sz
            dir_file_count += 1
            mtime = datetime.fromtimestamp(f.stat().st_mtime) if f.stat().st_mtime else None
            if mtime and (latest_mtime is None or mtime > latest_mtime):
                latest_mtime = mtime
            dir_files.append(LocalArtifactFile(
                name=f.name,
                relative_path=f.relative_to(ARTIFACTS_ROOT).as_posix(),
                size_bytes=sz,
                size_text=_format_size_text(sz),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    dir_files.sort(key=lambda x: x.name)
    task_id = entry.name if entry.name.startswith("task-") else None
    task = db.query(Task).filter(Task.task_id == task_id).first() if task_id and db is not None else None
    metadata = _build_task_display_metadata(
        task,
        db,
        dir_name=entry.name,
        path=entry.name,
        source="local_artifact",
        fallback_origin="本地遗留结果",
        file_names=[f.name for f in dir_files],
    ) if db is not None else {}

    directories.append(LocalArtifactDirectory(
        name=entry.name,
        relative_path=entry.name,
        file_count=dir_file_count,
        size_bytes=dir_size,
        size_text=_format_size_text(dir_size),
        modified_at=latest_mtime,
        task_id=task_id,
        task_display_name=metadata.get("display_title", ""),
        display_title=metadata.get("display_title", ""),
        server_name=metadata.get("server_name", ""),
        task_type_label=metadata.get("task_type_label", ""),
        script_label=metadata.get("script_label", ""),
        date_label=metadata.get("date_label", ""),
        dir_name=entry.name,
        path=entry.name,
        source="local_artifact",
        found_in_db=bool(metadata.get("found_in_db", False)),
        batch_id=metadata.get("batch_id"),
        inferred_batch_key=metadata.get("inferred_batch_key"),
        is_batch_task=bool(metadata.get("is_batch_task", False)),
        task_source_label=metadata.get("task_source_label", "未匹配"),
        task_status=metadata.get("task_status", ""),
        sequence_index=metadata.get("sequence_index"),
        files=dir_files,
    ))
    return dir_file_count, dir_size


# ───── Local artifacts delete ─────


@router.post("/local-artifacts/delete", response_model=LocalArtifactsDeleteResponse)
def delete_local_artifacts(
    payload: LocalArtifactsDeleteRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> LocalArtifactsDeleteResponse:
    """Delete specified paths under the artifacts directory."""
    deleted: list[DeleteResultItem] = []
    failed: list[DeleteResultItem] = []

    logger.info("[cleanup] delete request paths=%s recursive=%s", payload.paths, payload.recursive)

    for relative in payload.paths:
        try:
            resolved = _resolve_artifact_path(relative)
            if not resolved.exists():
                failed.append(DeleteResultItem(path=relative, success=False, error="path not found"))
                continue

            if resolved.is_dir() and not payload.recursive:
                try:
                    if any(resolved.iterdir()):
                        failed.append(DeleteResultItem(
                            path=relative, success=False,
                            error="directory is not empty, use recursive=true",
                        ))
                        continue
                except OSError as exc:
                    failed.append(DeleteResultItem(path=relative, success=False, error=str(exc)))
                    continue

            if resolved.is_file():
                resolved.unlink()
                logger.info("[cleanup] deleted file: %s", resolved)
            elif resolved.is_dir():
                shutil.rmtree(resolved)
                logger.info("[cleanup] deleted directory: %s", resolved)
            else:
                failed.append(DeleteResultItem(path=relative, success=False, error="not a file or directory"))
                continue

            deleted.append(DeleteResultItem(path=relative, success=True))
            _hide_task_from_history_for_artifact_delete(db, relative)

        except HTTPException as exc:
            failed.append(DeleteResultItem(path=relative, success=False, error=exc.detail))
        except OSError as exc:
            logger.error("[cleanup] delete error: %s", exc)
            failed.append(DeleteResultItem(path=relative, success=False, error=str(exc)))

    logger.info("[cleanup] delete done deleted=%d failed=%d", len(deleted), len(failed))
    write_audit_log(
        db, action="cleanup.local_artifacts.delete", target_type="cleanup", status="success" if deleted else "failed",
        actor="admin",
        target_name=f"{len(deleted)} deleted / {len(failed)} failed",
        message=f"deleted {len(deleted)} local artifact dirs, {len(failed)} failed",
        detail={"paths": payload.paths, "deleted": len(deleted), "failed": len(failed), "recursive": payload.recursive},
    )
    return LocalArtifactsDeleteResponse(deleted=deleted, failed=failed)


# ───── Remote single-server scan ─────


@router.post("/remote/scan", response_model=RemoteScanResult)
def scan_remote(
    payload: RemoteScanRequest,
    db: Session = Depends(get_db),
) -> RemoteScanResult:
    """Scan fixed remote directories on a single server."""
    start = monotonic()
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")

    logger.info("[cleanup] remote scan start server_id=%d host=%s", server.id, server.host)

    items: list[RemoteDirInfo] = []
    error: str | None = None
    remote_user = server.username or ""
    remote_home = ""
    now = datetime.now()

    executor = SSHExecutor(timeout=3)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        try:
            remote_home = executor.get_remote_home()
        except SSHExecutorError:
            logger.warning("[cleanup] remote scan get_remote_home failed server_id=%d, using fallback", server.id)
        try:
            remote_user = executor.exec_simple("whoami").strip()
        except SSHExecutorError:
            logger.warning("[cleanup] remote scan whoami failed server_id=%d, fallback to username=%s", server.id, server.username)

        # Fallback remote_home if it came back empty
        if not remote_home:
            if remote_user == "root":
                remote_home = "/root"
            else:
                remote_home = f"/home/{remote_user}"

        for target_key in ("tasks", "downloads", "tmp"):
            raw_target = REMOTE_TARGETS[target_key]
            actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

            exists = False
            size_text = ""
            file_count = 0

            try:
                test_cmd = f"test -d {shell_quote(actual_path)}"
                exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
                exists = (exit_code == 0)

                if exists:
                    du_cmd = f"du -sh {shell_quote(actual_path)} 2>/dev/null | cut -f1"
                    size_text = executor.exec_simple(du_cmd).strip()
                    count_cmd = f"find {shell_quote(actual_path)} -type f 2>/dev/null | wc -l"
                    count_out = executor.exec_simple(count_cmd).strip()
                    file_count = int(count_out) if count_out.isdigit() else 0
            except SSHExecutorError as exc:
                logger.warning("[cleanup] remote scan target=%s error=%s", target_key, exc)

            items.append(RemoteDirInfo(
                label=_target_label(target_key),
                remote_path=actual_path,
                exists=exists,
                size_text=size_text,
                file_count=file_count,
            ))

        # ── 扫描任务级子目录 ──
        tasks_path = REMOTE_TARGETS["tasks"].replace("$HOME", remote_home.rstrip("/"))
        task_dirs: list[RemoteTaskDirInfo] = []
        if tasks_path:
            try:
                test_cmd = f"test -d {shell_quote(tasks_path)}"
                ec, _o, _e = executor.exec_capture(test_cmd, timeout_seconds=5)
                if ec == 0:
                    # 使用 find 扫描 tasks/ 下二级子目录（stress/xxx, script/xxx 等）
                    find_cmd = f"find {shell_quote(tasks_path)} -mindepth 2 -maxdepth 2 -type d 2>/dev/null"
                    try:
                        find_out = executor.exec_simple(find_cmd).strip()
                    except SSHExecutorError:
                        find_out = ""
                    if find_out:
                        for _fp in find_out.split("\n"):
                            _fp = _fp.strip()
                            if not _fp:
                                continue
                            _dn = _fp.rstrip("/").split("/")[-1]
                            _parent = _fp.rstrip("/").split("/")[-2] if "/" in _fp else ""
                            _d_size = ""
                            _d_count = 0
                            _d_mtime: datetime | None = None
                            try:
                                _du = f"du -sh {shell_quote(_fp)} 2>/dev/null | cut -f1"
                                _d_size = executor.exec_simple(_du).strip()
                                _cnt = f"find {shell_quote(_fp)} -type f 2>/dev/null | wc -l"
                                _co = executor.exec_simple(_cnt).strip()
                                _d_count = int(_co) if _co.isdigit() else 0
                                _mt = executor.exec_simple(f"stat -c %Y {shell_quote(_fp)} 2>/dev/null").strip()
                                _d_mtime = datetime.fromtimestamp(int(_mt)) if _mt.isdigit() else None
                            except SSHExecutorError:
                                pass
                            task = _find_task_by_remote_dir(db, _fp, _dn)
                            metadata = _build_task_display_metadata(
                                task,
                                db,
                                dir_name=_dn,
                                path=_fp,
                                source="remote_task_dir",
                                fallback_origin="远端遗留结果",
                            )
                            task_dirs.append(RemoteTaskDirInfo(
                                dir_name=_dn,
                                remote_path=_fp,
                                exists=True,
                                size_text=_d_size,
                                file_count=_d_count,
                                modified_at=_d_mtime,
                                task_type_label=metadata["task_type_label"],
                                task_id=metadata["task_id"],
                                task_id_display=metadata["task_id"] or "未匹配",
                                remote_title=_dn,
                                display_title=metadata["display_title"],
                                server_name=metadata["server_name"],
                                script_label=metadata["script_label"],
                                date_label=metadata["date_label"],
                                path=_fp,
                                source="remote_task_dir",
                                found_in_db=metadata["found_in_db"],
                                matched=bool(metadata["task_id"]),
                                batch_id=metadata["batch_id"],
                                inferred_batch_key=metadata["inferred_batch_key"],
                                is_batch_task=metadata["is_batch_task"],
                                task_source_label=metadata["task_source_label"],
                                delete_key=_build_task_dir_delete_key(server.id, _fp),
                            ))
            except SSHExecutorError:
                logger.warning("[cleanup] remote scan task dirs failed server_id=%d", server.id)

        logger.info("[cleanup] remote scan done server_id=%d elapsed=%.3fs", server.id, monotonic() - start)
        task_dirs.sort(key=_sort_timestamp_from_remote_dir, reverse=True)

        # Success → online, set last_check_at, clear last_error
        server.status = "online"
        server.last_check_at = now
        server.last_error = None
        db.commit()

    except SSHExecutorError as exc:
        logger.error("[cleanup] remote scan failed server_id=%d error=%s", server.id, exc)
        error = str(exc)
        # Failure → offline, set last_error, do NOT update last_check_at
        server.status = "offline"
        server.last_error = str(exc)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[cleanup] remote scan unexpected error server_id=%d error=%s", server.id, exc)
        error = str(exc)
        server.status = "offline"
        server.last_error = str(exc)
        db.commit()
    finally:
        executor.close()

    return RemoteScanResult(server_id=server.id, remote_user=remote_user, remote_home=remote_home, items=items, error=error, task_dirs=task_dirs)


# ───── Remote scan-all (all online servers) ─────


def _scan_remote_server_worker(server_data: dict[str, Any]) -> RemoteServerScanResult:
    """Worker function to scan one remote server. Runs in thread pool.
    Updates server.status / last_check_at / last_error in its own DB session.
    """
    server_id: int = server_data["id"]
    server_name: str = server_data["name"]
    host: str = server_data["host"]
    port: int = server_data["port"]
    username: str = server_data["username"]
    auth_type: str = server_data["auth_type"]
    password: str | None = server_data.get("password")
    key_path: str | None = server_data.get("key_path")

    directories: list[RemoteDirectoryScan] = []
    remote_user = username or ""
    remote_home = ""
    now = datetime.now()
    db = SessionLocal()
    try:
        executor = SSHExecutor(timeout=3)
        executor.connect(
            host=host,
            port=port,
            username=username,
            **_server_auth_kwargs_raw(auth_type, password, key_path),
        )
        try:
            remote_home = executor.get_remote_home()
        except SSHExecutorError:
            logger.warning("[cleanup] scan-all get_remote_home failed server_id=%d, using fallback", server_id)
        try:
            remote_user = executor.exec_simple("whoami").strip()
        except SSHExecutorError:
            logger.warning("[cleanup] scan-all whoami failed server_id=%d, fallback to username=%s", server_id, username)

        # Fallback remote_home if it came back empty
        if not remote_home:
            if remote_user == "root":
                remote_home = "/root"
            else:
                remote_home = f"/home/{remote_user}"

        for target_key in ("tasks", "downloads", "tmp"):
            raw_target = REMOTE_TARGETS[target_key]
            actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

            exists = False
            size_text = ""
            file_count = 0

            try:
                test_cmd = f"test -d {shell_quote(actual_path)}"
                exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
                exists = (exit_code == 0)

                if exists:
                    du_cmd = f"du -sh {shell_quote(actual_path)} 2>/dev/null | cut -f1"
                    size_text = executor.exec_simple(du_cmd).strip()
                    count_cmd = f"find {shell_quote(actual_path)} -type f 2>/dev/null | wc -l"
                    count_out = executor.exec_simple(count_cmd).strip()
                    file_count = int(count_out) if count_out.isdigit() else 0
            except SSHExecutorError:
                pass

            directories.append(RemoteDirectoryScan(
                target=target_key,
                label=_target_label(target_key),
                remote_path=actual_path,
                exists=exists,
                size_text=size_text,
                file_count=file_count,
            ))

        # ── 扫描任务级子目录 ──
        _task_dirs: list[RemoteTaskDirInfo] = []
        _tp = REMOTE_TARGETS["tasks"].replace("$HOME", remote_home.rstrip("/"))
        if _tp:
            try:
                _tc = f"test -d {shell_quote(_tp)}"
                _ec, _o, _e = executor.exec_capture(_tc, timeout_seconds=5)
                if _ec == 0:
                    _find = f"find {shell_quote(_tp)} -mindepth 2 -maxdepth 2 -type d 2>/dev/null"
                    _out = executor.exec_simple(_find).strip()
                    if _out:
                        for _fp in _out.split(chr(10)):
                            _fp = _fp.strip()
                            if not _fp:
                                continue
                            _dn = _fp.rstrip("/").split("/")[-1]
                            _ds, _dc = "", 0
                            _dm: datetime | None = None
                            try:
                                _ds = executor.exec_simple(f"du -sh {shell_quote(_fp)} 2>/dev/null | cut -f1").strip()
                                _co = executor.exec_simple(f"find {shell_quote(_fp)} -type f 2>/dev/null | wc -l").strip()
                                _dc = int(_co) if _co.isdigit() else 0
                                _mt = executor.exec_simple(f"stat -c %Y {shell_quote(_fp)} 2>/dev/null").strip()
                                _dm = datetime.fromtimestamp(int(_mt)) if _mt.isdigit() else None
                            except SSHExecutorError:
                                pass
                            task = _find_task_by_remote_dir(db, _fp, _dn)
                            metadata = _build_task_display_metadata(
                                task,
                                db,
                                dir_name=_dn,
                                path=_fp,
                                source="remote_task_dir",
                                fallback_origin="远端遗留结果",
                            )
                            _task_dirs.append(RemoteTaskDirInfo(
                                dir_name=_dn, remote_path=_fp, exists=True,
                                size_text=_ds, file_count=_dc, modified_at=_dm,
                                task_type_label=metadata["task_type_label"],
                                task_id=metadata["task_id"],
                                task_id_display=metadata["task_id"] or "未匹配",
                                remote_title=_dn,
                                display_title=metadata["display_title"],
                                server_name=metadata["server_name"],
                                script_label=metadata["script_label"],
                                date_label=metadata["date_label"],
                                path=_fp,
                                source="remote_task_dir",
                                found_in_db=metadata["found_in_db"],
                                matched=bool(metadata["task_id"]),
                                batch_id=metadata["batch_id"],
                                inferred_batch_key=metadata["inferred_batch_key"],
                                is_batch_task=metadata["is_batch_task"],
                                task_source_label=metadata["task_source_label"],
                                delete_key=_build_task_dir_delete_key(server_id, _fp),
                            ))
            except SSHExecutorError:
                pass

        executor.close()
        _task_dirs.sort(key=_sort_timestamp_from_remote_dir, reverse=True)

        # Update server: success → online, set last_check_at, clear last_error
        svr = db.query(Server).filter(Server.id == server_id).first()
        if svr:
            svr.status = "online"
            svr.last_check_at = now
            svr.last_error = None
            db.commit()

        return RemoteServerScanResult(
            server_id=server_id,
            server_name=server_name,
            host=host,
            remote_user=remote_user,
            remote_home=remote_home,
            status="success",
            server_status="online",
            directories=directories,
            task_dirs=_task_dirs,
        )

    except Exception as exc:
        try:
            executor.close()
        except Exception:
            pass

        # Update server: failure → offline, set last_error, do NOT update last_check_at
        svr = db.query(Server).filter(Server.id == server_id).first()
        if svr:
            svr.status = "offline"
            svr.last_error = str(exc)
            db.commit()

        err_msg = str(exc)
        return RemoteServerScanResult(
            server_id=server_id,
            server_name=server_name,
            host=host,
            status="error",
            server_status="offline",
            message=f"SSH 连接失败，已标记离线：{err_msg}",
            error=err_msg,
            directories=[],
        )
    finally:
        db.close()


@router.post("/remote/scan-all", response_model=RemoteScanAllResult)
def scan_all_remote(
    db: Session = Depends(get_db),
    tag: str | None = Query(None, max_length=30),
) -> RemoteScanAllResult:
    """Scan all online servers' remote directories concurrently."""
    q = db.query(Server).filter(Server.status == "online")
    if tag:
        q = q.filter(Server.tags_json.contains(f'"{tag}"'))
    servers = q.all()
    total = len(servers)

    if total == 0:
        return RemoteScanAllResult(total_servers=0, success=0, failed=0, items=[])

    # Build serializable server data dicts
    server_list: list[dict[str, Any]] = [
        {
            "id": s.id,
            "name": s.name,
            "host": s.host,
            "port": s.port,
            "username": s.username,
            "auth_type": s.auth_type,
            "password": s.password,
            "key_path": s.key_path,
        }
        for s in servers
    ]

    results: list[RemoteServerScanResult] = []
    max_workers = min(total, 10)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_remote_server_worker, sd): sd for sd in server_list}

        for future in as_completed(futures):
            sd = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                results.append(RemoteServerScanResult(
                    server_id=sd["id"],
                    server_name=sd["name"],
                    host=sd["host"],
                    status="error",
                    error=str(exc),
                ))

    success_count = sum(1 for r in results if r.status == "success")
    failed_count = sum(1 for r in results if r.status == "error")

    # Keep stable order by server_id
    results.sort(key=lambda r: r.server_id)

    return RemoteScanAllResult(
        total_servers=total,
        success=success_count,
        failed=failed_count,
        items=results,
    )


# ───── Remote single-server delete ─────


@router.post("/remote/delete", response_model=RemoteDeleteResponse)
def delete_remote(
    payload: RemoteDeleteRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> RemoteDeleteResponse:
    """Delete a fixed remote directory's contents."""
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")

    if payload.target not in REMOTE_ALLOWED_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid target: {payload.target}. allowed: {', '.join(sorted(REMOTE_ALLOWED_TARGETS))}",
        )

    raw_target = REMOTE_TARGETS[payload.target]
    logger.info(
        "[cleanup] remote delete start server_id=%d host=%s target=%s",
        server.id, server.host, payload.target,
    )

    executor = SSHExecutor(timeout=30)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        remote_home = executor.get_remote_home()
        actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

        logger.info("[cleanup] remote delete resolved path: %s", actual_path)

        test_cmd = f"test -d {shell_quote(actual_path)}"
        exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
        if exit_code != 0:
            msg = f"directory does not exist, nothing to delete: {actual_path}"
            logger.info("[cleanup] remote delete: %s", msg)
            write_audit_log(
                db, action="cleanup.remote.delete", target_type="cleanup", status="success",
                actor="admin",
                server_id=server.id, server_name=server.name,
                target_name=payload.target,
                message=msg,
                detail={"target": payload.target, "remote_path": actual_path, "server_id": server.id},
            )
            return RemoteDeleteResponse(
                server_id=server.id,
                target=payload.target,
                remote_path=actual_path,
                success=True,
                message=msg,
            )

        clean_cmd = f"find {shell_quote(actual_path)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +"
        logger.info("[cleanup] remote delete command: %s", clean_cmd)
        executor.exec_simple(clean_cmd)

        logger.info("[cleanup] remote delete success server_id=%d target=%s", server.id, payload.target)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="success",
            actor="admin",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"cleaned: {actual_path}",
            detail={"target": payload.target, "remote_path": actual_path, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path=actual_path,
            success=True,
            message=f"cleaned: {actual_path}",
        )

    except SSHExecutorError as exc:
        logger.error("[cleanup] remote delete failed server_id=%d target=%s error=%s", server.id, payload.target, exc)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="failed",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"SSH error: {exc}",
            detail={"target": payload.target, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path="",
            success=False,
            message=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[cleanup] remote delete unexpected error server_id=%d target=%s error=%s", server.id, payload.target, exc)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="failed",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"unexpected error: {exc}",
            detail={"target": payload.target, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path="",
            success=False,
            message=str(exc),
        )
    finally:
        executor.close()


# ───── Remote task dir delete (single task directory) ─────

_TASK_DIR_ALLOWED_PREFIXES = (
    "gpu_stress_",
    "cpu_mem_stress_",
    "disk_stress_",
    "task-",
)


def _is_safe_task_dir_path(remote_path: str) -> bool:
    """Validate that a path is a safe, task-level directory for deletion."""
    if not remote_path:
        return False
    if remote_path == "/":
        return False
    if ".." in remote_path.split("/"):
        return False
    for bad in (";", "&", "|", "`", "$("):
        if bad in remote_path:
            return False
    # Must contain hpcdeploy/tasks/ in the path
    if "/hpcdeploy/tasks/" not in remote_path:
        return False
    # Must not be the tasks root itself
    parts = remote_path.rstrip("/").split("/")
    if parts[-1] in ("tasks", "stress", "script", "apptainer", "downloads", "tmp"):
        return False
    # Directory name must match an allowed prefix
    dir_name = parts[-1]
    if not any(dir_name.startswith(p) for p in _TASK_DIR_ALLOWED_PREFIXES):
        return False
    return True


@router.post("/remote/task-dir/delete", response_model=RemoteTaskDirDeleteResponse)
def delete_remote_task_dir(
    payload: RemoteTaskDirDeleteRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> RemoteTaskDirDeleteResponse:
    """Delete a single task directory on a remote server. Path is validated server-side."""
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")

    task_dir_path = _parse_task_dir_delete_key(payload.delete_key, server.id)
    logger.info("[cleanup] remote task-dir delete start server_id=%d host=%s path=%s",
                server.id, server.host, task_dir_path)

    if not _is_safe_task_dir_path(task_dir_path):
        logger.warning("[cleanup] remote task-dir delete refused: unsafe path %s", task_dir_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsafe task directory path: {task_dir_path}",
        )

    executor = SSHExecutor(timeout=30)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )

        # Check dir exists
        test_cmd = f"test -d {shell_quote(task_dir_path)}"
        ec, _o, _e = executor.exec_capture(test_cmd, timeout_seconds=10)
        if ec != 0:
            msg = f"directory does not exist: {task_dir_path}"
            logger.info("[cleanup] remote task-dir delete: %s", msg)
            return RemoteTaskDirDeleteResponse(
                server_id=server.id, task_dir_path=task_dir_path,
                success=True, message=msg,
            )

        cmd = f"rm -rf -- {shell_quote(task_dir_path)}"
        executor.exec_simple(cmd)

        logger.info("[cleanup] remote task-dir delete success server_id=%d path=%s", server.id, task_dir_path)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="success",
            actor="admin",
            server_id=server.id, server_name=server.name,
            target_name=Path(task_dir_path).name,
            message=f"deleted task dir: {task_dir_path}",
            detail={"task_dir_path": task_dir_path, "server_id": server.id},
        )
        return RemoteTaskDirDeleteResponse(
            server_id=server.id, task_dir_path=task_dir_path,
            success=True, message=f"deleted: {task_dir_path}",
        )
    except SSHExecutorError as exc:
        return RemoteTaskDirDeleteResponse(
            server_id=server.id, task_dir_path=task_dir_path,
            success=False, message=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        return RemoteTaskDirDeleteResponse(
            server_id=server.id, task_dir_path=task_dir_path,
            success=False, message=str(exc),
        )
    finally:
        executor.close()


# ───── Apptainer image scan (read-only) ─────

APPTAINER_DIR = BACKEND_ROOT / "apptainer"


@router.get("/apptainer/scan", response_model=ApptainerImageScanResult)
def scan_apptainer_images() -> ApptainerImageScanResult:
    """Scan the local apptainer directory for .sif files (read-only)."""
    start = monotonic()
    logger.info("[cleanup] apptainer scan start root=%s", APPTAINER_DIR)

    if not APPTAINER_DIR.is_dir():
        logger.info("[cleanup] apptainer scan done — root not found (elapsed=%.3fs)", monotonic() - start)
        return ApptainerImageScanResult(
            root=str(APPTAINER_DIR),
            total_files=0,
            total_size_bytes=0,
            items=[],
        )

    items: list[ApptainerImageItem] = []
    total_size = 0

    for entry in APPTAINER_DIR.rglob("*.sif"):
        if not entry.is_file():
            continue
        try:
            rel = entry.relative_to(APPTAINER_DIR).as_posix()
            size = entry.stat().st_size
            total_size += size
            mtime = datetime.fromtimestamp(entry.stat().st_mtime) if entry.stat().st_mtime else None
            items.append(ApptainerImageItem(
                filename=entry.name,
                relative_path=rel,
                size_bytes=size,
                size_text=_format_size_text(size),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    items.sort(key=lambda x: x.filename)

    logger.info(
        "[cleanup] apptainer scan done total_files=%d total_size=%d elapsed=%.3fs",
        len(items), total_size, monotonic() - start,
    )
    return ApptainerImageScanResult(
        root=str(APPTAINER_DIR),
        total_files=len(items),
        total_size_bytes=total_size,
        items=items,
    )
