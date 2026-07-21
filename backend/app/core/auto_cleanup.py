import asyncio
import fcntl
import logging
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.gpu_driver_runner import GPU_DRIVER_UPLOAD_ROOT
from app.core.audit import write_audit_log
from app.core.task_runner import TASK_LEASE_SECONDS, _attempt_stress_recovery, _stress_recovery_monitor
from app.core.time_utils import beijing_now
from app.db.database import SessionLocal
from app.models.settings import SystemSetting
from app.models.task import Task
from app.models.task_log import TaskLog
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ACTIVE_TASK_STATUSES = frozenset({"PENDING", "CONNECTING", "PREPARING", "UPLOADING", "WAITING_REBOOT", "RUNNING"})
GPU_DRIVER_UPLOAD_RETENTION_DAYS = 7
@dataclass
class AutoCleanupConfig:
    enabled: bool
    retention_days: int
    cleanup_time: str


@dataclass
class AutoCleanupResult:
    deleted_dirs: int = 0
    deleted_log_rows: int = 0
    freed_bytes: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    status: str = "skipped"
    message: str = ""


def start_auto_cleanup_scheduler() -> asyncio.Task[None]:
    """Start lightweight daily local artifacts cleanup loop."""
    return asyncio.create_task(_auto_cleanup_loop(), name="local-artifacts-auto-cleanup")


async def _auto_cleanup_loop() -> None:
    while True:
        try:
            wait_seconds = _seconds_until_next_check()
            await asyncio.sleep(wait_seconds)
            await asyncio.to_thread(run_due_auto_cleanup)
            await asyncio.to_thread(run_due_gpu_driver_upload_cleanup)
            await asyncio.to_thread(recover_stuck_stress_tasks)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("[auto-cleanup] scheduler iteration failed", exc_info=True)
            await asyncio.sleep(60)


def _seconds_until_next_check() -> float:
    now = beijing_now()
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return max((next_minute - now).total_seconds(), 1.0)


def run_due_auto_cleanup() -> AutoCleanupResult | None:
    db = SessionLocal()
    lock_file = None
    try:
        config = _load_config(db)
        if not config.enabled:
            return None

        now = beijing_now()
        if now.strftime("%H:%M") != config.cleanup_time:
            return None

        lock_file = _try_acquire_cleanup_lock()
        if lock_file is None:
            return None

        today = now.date().isoformat()
        if _get_setting(db, "auto_cleanup_last_run_date", "") == today:
            return None

        _set_setting(db, "auto_cleanup_last_run_date", today)
        db.commit()
        return run_local_artifacts_auto_cleanup(db, config.retention_days)
    except Exception:
        db.rollback()
        logger.warning("[auto-cleanup] due cleanup failed", exc_info=True)
        return None
    finally:
        if lock_file is not None:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except OSError:
                pass
        db.close()


def run_due_gpu_driver_upload_cleanup() -> int:
    """Delete expired custom installers while preserving active task sources."""
    now = beijing_now()
    if now.strftime("%H:%M") != "03:10":
        return 0
    db = SessionLocal()
    try:
        today = now.date().isoformat()
        if _get_setting(db, "gpu_driver_upload_cleanup_last_run_date", "") == today:
            return 0
        _set_setting(db, "gpu_driver_upload_cleanup_last_run_date", today)
        cutoff = datetime.utcnow() - timedelta(days=GPU_DRIVER_UPLOAD_RETENTION_DAYS)
        active_ids = {
            str((task.params or {}).get("driver_upload_id"))
            for task in db.query(Task).filter(Task.status.in_(ACTIVE_TASK_STATUSES)).all()
            if (task.params or {}).get("driver_upload_id")
        }
        deleted = 0
        if GPU_DRIVER_UPLOAD_ROOT.is_dir():
            for path in GPU_DRIVER_UPLOAD_ROOT.glob("*.run"):
                if path.stem in active_ids or datetime.utcfromtimestamp(path.stat().st_mtime) >= cutoff:
                    continue
                path.unlink()
                deleted += 1
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        logger.warning("[gpu-driver-upload-cleanup] failed", exc_info=True)
        return 0
    finally:
        db.close()


def _try_acquire_cleanup_lock():
    lock_dir = ARTIFACTS_DIR.parent
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = (lock_dir / ".auto_cleanup.lock").open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except BlockingIOError:
        lock_file.close()
        return None


def run_local_artifacts_auto_cleanup(db: Session, retention_days: int) -> AutoCleanupResult:
    result = AutoCleanupResult()
    started_at = datetime.utcnow()
    cutoff = started_at - timedelta(days=retention_days)
    artifacts_root = ARTIFACTS_DIR.resolve()
    result.deleted_log_rows = _delete_expired_task_logs(db, cutoff)

    if not artifacts_root.is_dir():
        result.status = "skipped"
        result.message = f"artifacts directory not found; deleted {result.deleted_log_rows} expired task log rows"
        _save_result(db, started_at, result)
        _write_summary_audit(db, result, retention_days)
        return result

    for entry in sorted(artifacts_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue

        dir_name = entry.name
        try:
            resolved = entry.resolve()
            resolved.relative_to(artifacts_root)

            task = db.query(Task).filter(Task.task_id == dir_name).first()
            if task is None and not dir_name.startswith("task-"):
                continue
            if task is not None and task.status in ACTIVE_TASK_STATUSES:
                result.skipped_count += 1
                _write_dir_audit(
                    db,
                    dir_name,
                    "skipped",
                    f"skip active task status={task.status}",
                    {"task_status": task.status, "retention_days": retention_days},
                )
                continue

            artifact_time = _task_retention_time(task) if task is not None else datetime.utcfromtimestamp(resolved.stat().st_mtime)
            if artifact_time >= cutoff:
                continue

            size_bytes = _directory_size(resolved)
            shutil.rmtree(resolved)
            result.deleted_dirs += 1
            result.freed_bytes += size_bytes
            _write_dir_audit(
                db,
                dir_name,
                "success",
                f"deleted local artifact dir, freed {size_bytes} bytes",
                {
                    "retention_days": retention_days,
                    "retention_time": artifact_time.isoformat(timespec="seconds"),
                    "freed_bytes": size_bytes,
                },
            )
        except Exception as exc:
            result.failed_count += 1
            logger.warning("[auto-cleanup] failed to clean artifact dir %s", dir_name, exc_info=True)
            _write_dir_audit(
                db,
                dir_name,
                "failed",
                str(exc),
                {"retention_days": retention_days},
            )

    result.status = "failed" if result.failed_count > 0 else "success"
    result.message = (
        f"deleted {result.deleted_dirs} local artifact dirs, "
        f"freed {result.freed_bytes} bytes, "
        f"deleted {result.deleted_log_rows} task log rows, "
        f"failed {result.failed_count}, skipped {result.skipped_count}"
    )
    _save_result(db, started_at, result)
    _write_summary_audit(db, result, retention_days)
    return result


def _task_retention_time(task: Task) -> datetime:
    """Use terminal time when available, otherwise task creation time."""
    return task.end_time or task.created_at


def _delete_expired_task_logs(db: Session, cutoff: datetime) -> int:
    expired_task_ids = [
        task_id
        for task_id, status, created_at, end_time in db.query(
            Task.task_id, Task.status, Task.created_at, Task.end_time
        ).all()
        if status not in ACTIVE_TASK_STATUSES and (end_time or created_at) < cutoff
    ]
    if not expired_task_ids:
        return 0
    deleted = (
        db.query(TaskLog)
        .filter(TaskLog.task_id.in_(expired_task_ids))
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(deleted or 0)


def _load_config(db: Session) -> AutoCleanupConfig:
    return AutoCleanupConfig(
        enabled=_str_to_bool(_get_setting(db, "auto_cleanup_enabled", "false")),
        retention_days=_str_to_int(_get_setting(db, "local_artifact_retention_days", "30"), 30),
        cleanup_time=_get_setting(db, "auto_cleanup_time", "03:00"),
    )


def _get_setting(db: Session, key: str, default: str) -> str:
    row = db.get(SystemSetting, key)
    return row.value if row is not None else default


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value


def _save_result(db: Session, started_at: datetime, result: AutoCleanupResult) -> None:
    values = {
        "auto_cleanup_last_run_at": started_at.isoformat(timespec="seconds"),
        "auto_cleanup_last_deleted_dirs": str(result.deleted_dirs),
        "auto_cleanup_last_deleted_log_rows": str(result.deleted_log_rows),
        "auto_cleanup_last_freed_bytes": str(result.freed_bytes),
        "auto_cleanup_last_failed_count": str(result.failed_count),
        "auto_cleanup_last_status": result.status,
        "auto_cleanup_last_message": result.message,
    }
    for key, value in values.items():
        _set_setting(db, key, value)
    db.commit()


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _write_dir_audit(db: Session, dir_name: str, status: str, message: str, detail: dict[str, object]) -> None:
    write_audit_log(
        db,
        action="auto_cleanup_local_artifacts",
        target_type="local_artifact",
        status=status,
        actor="system",
        target_id=dir_name,
        target_name=dir_name,
        task_id=dir_name,
        message=message,
        detail=detail,
    )


def _write_summary_audit(db: Session, result: AutoCleanupResult, retention_days: int) -> None:
    write_audit_log(
        db,
        action="auto_cleanup_local_artifacts",
        target_type="local_artifact",
        status=result.status,
        actor="system",
        target_name="summary",
        message=result.message,
        detail={
            "retention_days": retention_days,
            "deleted_dirs": result.deleted_dirs,
            "deleted_log_rows": result.deleted_log_rows,
            "freed_bytes": result.freed_bytes,
            "failed_count": result.failed_count,
            "skipped_count": result.skipped_count,
        },
    )


def _str_to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _str_to_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def recover_stuck_stress_tasks() -> int:
    """Second-layer guard: recover stress tasks stuck in RUNNING with expired leases.

    The primary poll-loop in _execute_stress_async now has try-except protection,
    but if the entire daemon thread somehow dies (e.g. process-level interruption),
    this periodic recovery will find and clean up orphaned RUNNING tasks.

    Recovery strategy:
    1. Find RUNNING stress tasks with expired leases
    2. If local artifacts already exist (from a prior partial collection), attempt recovery
    3. Otherwise, renew the lease and attach an SSH recovery monitor.  An
       expired local lease alone is not proof that a remote stress process died.
    """
    db = SessionLocal()
    recovered = 0
    try:
        now = datetime.utcnow()
        stale_tasks = (
            db.query(Task)
            .filter(
                Task.status == "RUNNING",
                Task.task_type == "stress",
                Task.lease_expire_time.isnot(None),
                Task.lease_expire_time < now,
            )
            .all()
        )
        for task in stale_tasks:
            _elapsed = ""
            if task.start_time:
                _delta = now - task.start_time
                _elapsed = f" (elapsed {int(_delta.total_seconds())}s)"
            db.add(TaskLog(
                task_id=task.task_id,
                level="WARN",
                message=(
                    f"stuck task recovery: RUNNING with expired lease{_elapsed}, "
                    f"lease_expire={task.lease_expire_time}"
                ),
            ))
            # Check if local artifacts exist (from prior partial collection)
            task_artifact_dir = ARTIFACTS_DIR / task.task_id
            if task_artifact_dir.is_dir() and _attempt_stress_recovery(db, task.task_id, task):
                recovered += 1
                continue
            # Lease expiry alone is insufficient to declare a long-running
            # stress task failed.  Prevent duplicate recoveries, then ask the
            # existing SSH recovery path to inspect the remote PID/report.
            task.last_heartbeat = now
            task.lease_expire_time = now + timedelta(seconds=TASK_LEASE_SECONDS)
            db.commit()
            db.add(TaskLog(
                task_id=task.task_id,
                level="SYSTEM",
                message="stuck task recovery: lease renewed; launching SSH recovery monitor",
            ))
            db.commit()
            threading.Thread(
                target=_stress_recovery_monitor,
                args=(task.task_id,),
                daemon=True,
                name=f"stress-lease-recovery-{task.task_id}",
            ).start()
            recovered += 1
        if stale_tasks:
            logger.info("[stuck-task-recovery] recovered %d/%d stuck stress tasks",
                        recovered, len(stale_tasks))
        return recovered
    except Exception:
        logger.warning("[stuck-task-recovery] iteration failed", exc_info=True)
        return recovered
    finally:
        db.close()
