from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.models.task import Task
from app.models.task_log import TaskLog


ACTIVE_RECOVERY_STATUSES = ("RUNNING", "CONNECTING", "PREPARING", "UPLOADING")
PRE_EXECUTION_STATUSES = ("CONNECTING", "PREPARING", "UPLOADING")
SCHEDULER_RECOVERED_MARKER = "scheduler recovered"
DEFAULT_STALE_AFTER_SECONDS = 600


@dataclass
class TaskRecoveryResult:
    active_reset: int = 0
    failed_reset: int = 0
    total: int = 0


def _is_stale(task: Task, now: datetime, stale_after: timedelta) -> bool:
    if task.lease_expire_time is not None:
        return task.lease_expire_time < now
    heartbeat = task.last_heartbeat or task.updated_at
    return heartbeat is not None and heartbeat < now - stale_after


def should_requeue_after_restart(task_status: str, is_stale: bool) -> bool:
    """Only retry work that had not reached remote command execution.

    A RUNNING task may outlive the backend by hours.  It is recovered by a
    remote PID monitor, never requeued merely because its local heartbeat is
    old; otherwise a restart could launch the same workload twice.
    """
    del is_stale
    return task_status in PRE_EXECUTION_STATUSES


def _reset_task_to_pending(task: Task, now: datetime, message: str) -> None:
    task.status = "PENDING"
    task.worker_id = None
    task.lease_expire_time = None
    task.last_heartbeat = None
    task.start_time = None
    task.end_time = None
    task.exit_code = None
    task.error_message = None
    task.updated_at = now


def recover_stuck_tasks(stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS) -> TaskRecoveryResult:
    """Recover queue state after backend/scheduler restart.

    Project status naming uses PENDING as the waiting state. This function only
    runs at backend startup and never deletes task history.
    """
    now = datetime.utcnow()
    stale_after = timedelta(seconds=stale_after_seconds)
    result = TaskRecoveryResult()
    db = SessionLocal()
    try:
        active_tasks = (
            db.query(Task)
            .filter(Task.status.in_(ACTIVE_RECOVERY_STATUSES))
            .all()
        )
        for task in active_tasks:
            if not should_requeue_after_restart(task.status, _is_stale(task, now, stale_after)):
                continue
            _reset_task_to_pending(
                task,
                now,
                f"startup recovery: stale {task.status} task reset to PENDING",
            )
            db.add(TaskLog(
                task_id=task.task_id,
                level="SYSTEM",
                message="startup recovery: stale active task reset to PENDING",
            ))
            result.active_reset += 1

        failed_tasks = (
            db.query(Task)
            .filter(Task.status == "FAILED")
            .filter(Task.error_message.ilike(f"%{SCHEDULER_RECOVERED_MARKER}%"))
            .all()
        )
        for task in failed_tasks:
            _reset_task_to_pending(
                task,
                now,
                "startup recovery: scheduler recovered failure reset to PENDING",
            )
            db.add(TaskLog(
                task_id=task.task_id,
                level="SYSTEM",
                message="startup recovery: scheduler recovered failure reset to PENDING",
            ))
            result.failed_reset += 1

        result.total = result.active_reset + result.failed_reset
        if result.total:
            db.commit()
        return result
    finally:
        db.close()
