import asyncio
import shutil
import re
import threading
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from time import sleep
from urllib.parse import quote

from app.core.batch_report_exporter import export_batch_report_zip
from app.core.report_summary import (
    get_cached_report_summary,
    schedule_report_summary_generation,
    unknown_report_summary,
)
from app.core.task_state_resolver import resolve_final_status
from app.core.task_serializer import serialize_task_record
from app.core.stress_params import (
    validate_stress_params,
    validate_stress_suite_params,
)
from app.core.script_library import get_library_file_record
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError, shell_quote
from app.core.script_validator import ScriptValidationError
from app.core.task_runner import (
    CANCELABLE_TASK_STATUSES,
    CANCELED_EXIT_CODE,
    PID_FILE_NAME,
    TERMINAL_TASK_STATUSES,
    UNFINISHED_TASK_STATUSES,
    _build_remote_pid_file_path,
    resume_running_stress_tasks_after_startup,
    run_task_stage8b,
)
from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.ws_manager import ws_manager
from app.db.database import SessionLocal, get_db
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.log import TaskLogRead
from app.schemas.task import (
    ArtifactFileDetail,
    ArtifactListResponse,
    BatchCancelItem,
    BatchCancelRequest,
    BatchCancelResponse,
    BatchDetailResponse,
    BatchSummaryItem,
    BatchSummaryListResponse,
    BatchTaskRetryResponse,
    BatchTaskCreateItem,
    BatchTaskCreateRequest,
    BatchTaskCreateResponse,
    BatchTaskDetailItem,
    StressSuiteCreateItem,
    StressSuiteCreateRequest,
    StressSuiteCreateResponse,
    TaskCancelRequest,
    TaskCancelResponse,
    TaskCleanupResponse,
    TaskDeleteResponse,
    TaskDiagnosisResponse,
    TaskListResponse,
    TaskMonitorRequest,
    TaskMonitorResponse,
    TaskMonitorResponseStructured,
    TaskRead,
    TaskRunRequest,
    TaskRunResponse,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

WS_DB_POLL_INTERVAL_SECONDS = 1.0

router = APIRouter(prefix="/tasks", tags=["tasks"])

MONITOR_TIMEOUT_SECONDS = 10
CLEANUP_TIMEOUT_SECONDS = 30
# Whitelist: script_name → list of allowed temp download dirs to clean up on cancel
SCRIPT_TEMP_DIR_MAP: dict[str, list[str]] = {
    "install_oneapi_2022.sh": ["/tmp/oneapi_install_2022"],
    "install_openmpi_4.1.6_aocc_aocl.sh": ["/tmp/openmpi_aocc_aocl_install"],
}
# Flat set of all allowed temp dirs for fast lookup
ALLOWED_TEMP_DIRS: set[str] = set()
for dirs in SCRIPT_TEMP_DIR_MAP.values():
    for d in dirs:
        ALLOWED_TEMP_DIRS.add(d)

APPTAINER_ALLOWED_PARAM_KEYS: set[str] = {"overwrite"}


def _validate_apptainer_params(raw: dict[str, object] | None) -> dict[str, object]:
    """Validate and sanitize apptainer task params.
    Only allows the 'overwrite' key (must be bool).
    Raises HTTPException(400) on any invalid value.
    Returns a cleaned params dict.
    """
    validated: dict[str, object] = {}

    if raw is None or len(raw) == 0:
        validated["overwrite"] = True
        return validated

    # Reject unknown keys
    for key in raw:
        if key not in APPTAINER_ALLOWED_PARAM_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown apptainer param: {key}",
            )

    # Validate overwrite
    if "overwrite" in raw:
        ow = raw["overwrite"]
        if not isinstance(ow, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="overwrite must be a boolean",
            )
        validated["overwrite"] = ow
    else:
        validated["overwrite"] = True

    return validated


MONITOR_COMMANDS: dict[str, str] = {
    "top": "top -b -n 1 | head -40",
    "free": "free -h",
    "ps": "ps -eo pid,ppid,user,%cpu,%mem,cmd --sort=-%cpu | head -20",
    "cpu_mem": "printf '[top]\\n'; top -b -n 1 | head -40; printf '\\n[free]\\n'; free -h; printf '\\n[ps]\\n'; ps -eo pid,ppid,user,%cpu,%mem,cmd --sort=-%cpu | head -20",
    "iostat": "if command -v iostat >/dev/null 2>&1; then iostat -dx 1 2; else printf 'iostat not found, please install sysstat\\n'; fi",
    "df": "df -h",
    "disk": "if command -v iostat >/dev/null 2>&1; then printf '[iostat]\\n'; iostat -dx 1 2; else printf 'iostat not found, please install sysstat\\n'; fi; printf '\\n[df]\\n'; df -h",
    "nvidia-smi": "if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi; else printf 'nvidia-smi not found or NVIDIA driver unavailable\\n'; fi",
    "gpu": "if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi; else printf 'nvidia-smi not found or NVIDIA driver unavailable\\n'; fi",
}

VALID_TASK_STATUSES: frozenset[str] = frozenset({
    "PENDING", "CONNECTING", "PREPARING", "UPLOADING",
    "RUNNING", "CANCELING", "SUCCESS", "FAILED", "CANCELED",
})
EXECUTING_TASK_STATUSES: frozenset[str] = frozenset({
    "CONNECTING", "PREPARING", "UPLOADING", "RUNNING", "CANCELING",
})
VALID_TASK_TYPES: frozenset[str] = frozenset({"script", "stress", "apptainer"})
VALID_ORDER_VALUES: frozenset[str] = frozenset({"created_desc", "created_asc"})
VALID_TASK_SCOPES: frozenset[str] = frozenset({"single", "batch"})


def _get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return task


def _get_server_or_400(db: Session, server_id: int) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="server_id not found")
    return server


@router.get("", response_model=TaskListResponse)
def list_tasks(
    db: Session = Depends(get_db),
    task_status: str | None = Query(None, alias="status"),
    task_type: str | None = Query(None),
    task_scope: str | None = Query(None, alias="scope"),
    server_id: int | None = Query(None, ge=1),
    keyword: str | None = Query(None, min_length=1),
    include_batch_context: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("created_desc"),
    active_only: bool = Query(False, description="only return tasks in active execution"),
) -> TaskListResponse:
    # --- parameter validation ---
    if task_status is not None and task_status not in VALID_TASK_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid status: {task_status}",
        )
    if task_type is not None and task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid task_type: {task_type}",
        )
    if task_scope is not None and task_scope not in VALID_TASK_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid scope: {task_scope}",
        )
    if order not in VALID_ORDER_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid order: {order}",
        )

    # --- build query ---
    query = db.query(Task).filter(Task.hidden_from_history == 0)

    if active_only is True:
        query = query.filter(Task.status.in_(EXECUTING_TASK_STATUSES))

    if task_type is not None:
        query = query.filter(Task.task_type == task_type)
    if task_scope == "single":
        query = query.filter(Task.batch_id.is_(None))
    elif task_scope == "batch":
        query = query.filter(Task.batch_id.isnot(None))
    if server_id is not None:
        query = query.filter(Task.server_id == server_id)
    if keyword is not None:
        like_pattern = f"%{keyword}%"
        query = query.outerjoin(Server, Task.server_id == Server.id)
        query = query.filter(
            or_(
                Task.task_id.ilike(like_pattern),
                Task.batch_id.ilike(like_pattern),
                Task.file_name.ilike(like_pattern),
                Task.file_path.ilike(like_pattern),
                Task.remote_work_dir.ilike(like_pattern),
                Task.error_message.ilike(like_pattern),
                Server.name.ilike(like_pattern),
                Server.host.ilike(like_pattern),
            )
        )

    if task_status is not None:
        matched_query = query.filter(Task.status == task_status)
        if include_batch_context is True:
            batch_ids = [
                batch_id
                for (batch_id,) in matched_query
                .filter(Task.batch_id.isnot(None))
                .with_entities(Task.batch_id)
                .distinct()
                .all()
            ]
            if batch_ids:
                # Keep matching single tasks status-filtered, while preserving every
                # subtask for batches that contain a matching task.
                query = query.filter(
                    or_(
                        Task.status == task_status,
                        Task.batch_id.in_(batch_ids),
                    )
                )
            else:
                query = matched_query
        else:
            query = matched_query

    # --- order ---
    if order == "created_asc":
        query = query.order_by(Task.id.asc())
    else:
        query = query.order_by(Task.id.desc())

    # --- total before pagination ---
    total = query.count()

    # --- pagination ---
    tasks = query.offset(offset).limit(limit).all()

    # --- serialize ---
    items = [_serialize_task(task, db) for task in tasks]
    return TaskListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/run", response_model=TaskRunResponse, status_code=status.HTTP_201_CREATED)
def run_task(
    payload: TaskRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TaskRunResponse:
    server = _get_server_or_400(db, payload.server_id)

    running_task = (
        db.query(Task)
        .filter(Task.server_id == payload.server_id, Task.status.in_(UNFINISHED_TASK_STATUSES))
        .first()
    )
    if running_task is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "server already has a running task",
                "running_task_id": running_task.task_id,
                "running_status": running_task.status,
            },
        )

    file_record = _get_library_file_or_400(payload.file_path)

    physical = file_record["physical_category"]
    if payload.task_type == "script":
        if physical in ("stress", "apptainer"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="script task_type only allows non-stress, non-apptainer scripts",
            )
    elif physical != payload.task_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_type does not match knowledge base file category",
        )

    params: dict[str, object] | None = None
    if payload.task_type == "stress":
        # Accept params dict if provided; otherwise fall back to top-level duration_seconds (legacy)
        raw_params: dict[str, object] = {}
        if payload.params is not None:
            raw_params = payload.params
        elif payload.duration_seconds is not None:
            raw_params = {"duration_seconds": payload.duration_seconds}

        if "duration_seconds" not in raw_params:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="duration_seconds is required for stress tasks")

        validated = validate_stress_params(raw_params, str(file_record["name"]))
        params = validated
    elif payload.task_type == "apptainer":
        params = _validate_apptainer_params(payload.params)
    elif payload.params is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="params is only allowed for stress and apptainer tasks",
        )

    remote_work_dir = _build_remote_work_dir(payload.task_type)
    command_preview = _build_command_preview(
        task_type=payload.task_type,
        file_name=str(file_record["name"]),
        params=params,
        remote_work_dir=remote_work_dir,
    )
    task_id = _generate_task_id()

    task = Task(
        task_id=task_id,
        server_id=server.id,
        script_id=None,
        task_type=payload.task_type,
        file_path=str(file_record["path"]),
        file_name=str(file_record["name"]),
        display_category=str(file_record["display_category"]),
        remote_work_dir=remote_work_dir,
        command_preview=command_preview,
        params=params,
        status="PENDING",
    )
    db.add(task)
    db.flush()
    db.add(
        TaskLog(
            task_id=task_id,
            level="SYSTEM",
            message="task created",
        )
    )
    db.commit()
    write_audit_log(
        db, action="task.create", target_type="task", status="success",
        actor="visitor",
        target_id=task_id, target_name=f"{server.name} · {file_record['name']}",
        server_id=server.id, server_name=server.name,
        task_id=task_id,
        message=f"created {payload.task_type} task on {server.name}",
        detail={"task_type": payload.task_type, "file_name": str(file_record["name"])},
    )
    background_tasks.add_task(run_task_stage8b, task_id)
    return TaskRunResponse(task_id=task_id, status="PENDING")


# ───── Batch task creation ─────

FORBIDDEN_PARAM_KEYS: frozenset[str] = frozenset({
    "command", "raw_args", "shell", "raw_command",
    "remote_path", "env", "target_dir", "delete", "chmod", "run", "exec",
})


def _start_task_thread(task_id: str) -> None:
    """Start a task runner in a background daemon thread for immediate concurrency."""
    thread = threading.Thread(target=run_task_stage8b, args=(task_id,), daemon=True)
    thread.start()


def _create_task_for_server(
    db: Session,
    server: Server,
    task_type: str,
    file_path: str,
    file_name: str,
    file_record: dict[str, object],
    params: dict[str, object] | None = None,
    batch_id: str | None = None,
) -> str:
    """Create a single task record for a server. Raises HTTPException on conflict.
    Does NOT start the task runner — caller is responsible for that.
    """
    running_task = (
        db.query(Task)
        .filter(Task.server_id == server.id, Task.status.in_(UNFINISHED_TASK_STATUSES))
        .first()
    )
    if running_task is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="server already has unfinished task",
        )

    remote_work_dir = _build_remote_work_dir(task_type)
    command_preview = _build_command_preview(
        task_type=task_type,
        file_name=file_name,
        params=params,
        remote_work_dir=remote_work_dir,
    )
    task_id = _generate_task_id()

    task = Task(
        task_id=task_id,
        server_id=server.id,
        script_id=None,
        task_type=task_type,
        file_path=str(file_record["path"]),
        file_name=str(file_record["name"]),
        display_category=str(file_record["display_category"]),
        remote_work_dir=remote_work_dir,
        command_preview=command_preview,
        params=params,
        status="PENDING",
        batch_id=batch_id,
    )
    db.add(task)
    db.flush()
    db.add(TaskLog(task_id=task_id, level="SYSTEM", message="task created"))
    db.commit()
    return task_id


@router.post("/batch", response_model=BatchTaskCreateResponse)
def batch_run_task(
    payload: BatchTaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> BatchTaskCreateResponse:
    # Reject forbidden param keys before any other validation
    for key in payload.params:
        if key in FORBIDDEN_PARAM_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"forbidden param key: {key}",
            )

    # Validate script file (reuses single-task validation)
    file_record = _get_library_file_or_400(payload.script_path)

    physical = file_record["physical_category"]
    if payload.script_type == "script":
        if physical in ("stress", "apptainer"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="script task_type only allows non-stress, non-apptainer scripts",
            )
    elif physical != payload.script_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="script_type does not match knowledge base file category",
        )

    # Validate params
    params: dict[str, object] | None = None
    if payload.script_type == "stress":
        if "duration_seconds" not in payload.params:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duration_seconds is required for stress tasks",
            )
        params = validate_stress_params(payload.params, script_name)
    elif payload.script_type == "apptainer":
        params = _validate_apptainer_params(payload.params)
    elif payload.params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="params is only allowed for stress and apptainer tasks",
        )

    # Deduplicate server_ids preserving order
    server_ids: list[int] = list(dict.fromkeys(payload.server_ids))

    # Generate batch_id for grouping
    now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand_suffix = token_hex(3)
    batch_id = f"batch-{now_str}-{rand_suffix}"

    items: list[BatchTaskCreateItem] = []
    created = 0
    skipped = 0
    failed = 0

    for sid in server_ids:
        server = db.get(Server, sid)
        if server is None:
            items.append(
                BatchTaskCreateItem(
                    server_id=sid,
                    server_name="unknown",
                    success=False,
                    status="FAILED",
                    reason="server not found",
                )
            )
            failed += 1
            continue

        if server.status != "online":
            items.append(
                BatchTaskCreateItem(
                    server_id=sid,
                    server_name=server.name,
                    success=False,
                    status="SKIPPED",
                    reason="server is offline",
                )
            )
            skipped += 1
            continue

        running = (
            db.query(Task)
            .filter(Task.server_id == sid, Task.status.in_(UNFINISHED_TASK_STATUSES))
            .first()
        )
        if running is not None:
            items.append(
                BatchTaskCreateItem(
                    server_id=sid,
                    server_name=server.name,
                    success=False,
                    status="SKIPPED",
                    reason="server already has unfinished task",
                )
            )
            skipped += 1
            continue

        try:
            task_id = _create_task_for_server(
                db, server, payload.script_type,
                payload.script_path, script_name, file_record,
                params,
                batch_id=batch_id,
            )
            # Start each task in its own daemon thread for true concurrency
            _start_task_thread(task_id)
            items.append(
                BatchTaskCreateItem(
                    server_id=sid,
                    server_name=server.name,
                    task_id=task_id,
                    success=True,
                    status="PENDING",
                )
            )
            created += 1
        except HTTPException as exc:
            detail = exc.detail
            if not isinstance(detail, str):
                detail = "task creation failed"
            items.append(
                BatchTaskCreateItem(
                    server_id=sid,
                    server_name=server.name,
                    success=False,
                    status="FAILED",
                    reason=detail,
                )
            )
            failed += 1

    write_audit_log(
        db, action="task.batch_create", target_type="task", status="success" if failed == 0 else "failed",
        actor="visitor",
        target_name=script_name,
        message=f"batch create {script_name}: {created} created, {skipped} skipped, {failed} failed",
        detail={"batch_id": batch_id, "script_type": payload.script_type, "script_name": script_name,
                "server_ids": server_ids, "created": created, "skipped": skipped, "failed": failed},
    )
    return BatchTaskCreateResponse(
        batch_id=batch_id,
        script_name=script_name,
        total=len(server_ids),
        created=created,
        skipped=skipped,
        failed=failed,
        items=items,
    )


# ── Stress suite (Phase 29A) ──

# Allowed stress suite scripts in fixed execution order (GPU → CPU/mem → Disk)
STRESS_SUITE_SCRIPTS: list[dict[str, str | int]] = [
    {"path": "scripts/stress/gpu_stress_report.sh",     "name": "gpu_stress_report.sh",     "seq": 1, "label": "GPU 压测"},
    {"path": "scripts/stress/cpu_mem_stress_report.sh", "name": "cpu_mem_stress_report.sh", "seq": 2, "label": "CPU/内存压测"},
    {"path": "scripts/stress/disk_stress_report.sh",    "name": "disk_stress_report.sh",    "seq": 3, "label": "磁盘压测"},
]
STRESS_SUITE_ALLOWED_PATHS: set[str] = {s["path"] for s in STRESS_SUITE_SCRIPTS}  # type: ignore
_STRESS_SUITE_SERVER_LOCKS: dict[int, threading.Lock] = {}
_STRESS_SUITE_SERVER_LOCKS_GUARD = threading.Lock()
STRESS_SUITE_LOCK_ACQUIRE_TIMEOUT_SECONDS = 5


def _get_stress_suite_server_lock(server_id: int) -> threading.Lock:
    with _STRESS_SUITE_SERVER_LOCKS_GUARD:
        lock = _STRESS_SUITE_SERVER_LOCKS.get(server_id)
        if lock is None:
            lock = threading.Lock()
            _STRESS_SUITE_SERVER_LOCKS[server_id] = lock
        return lock


def _fail_suite_task_records_for_scheduler(db: Session, task_records: list[Task], message: str) -> int:
    failed = 0
    for task in task_records:
        if task.status not in UNFINISHED_TASK_STATUSES:
            continue
        task.status = "FAILED"
        task.end_time = datetime.utcnow()
        task.error_message = message[:500]
        db.add(TaskLog(task_id=task.task_id, level="ERROR", message=message[:1000]))
        failed += 1

    if failed:
        db.commit()
        for task in task_records:
            if task.status == "FAILED":
                schedule_report_summary_generation(task.task_id)
                try:
                    ws_manager.broadcast_status_sync(task.task_id, "FAILED")
                    ws_manager.broadcast_done_sync(task.task_id, "FAILED")
                except Exception:
                    pass
    return failed


def _mark_stress_suite_scheduler_blocked(db: Session, server_id: int, batch_id: str, message: str) -> int:
    task_records = (
        db.query(Task)
        .filter(Task.batch_id == batch_id, Task.server_id == server_id)
        .order_by(Task.sequence_index)
        .all()
    )
    return _fail_suite_task_records_for_scheduler(db, task_records, message)


def recover_orphaned_stress_suite_pending_tasks() -> int:
    """Fail stress-suite tasks that cannot resume after backend restart.

    Stress-suite workers are daemon threads kept in process memory. If the backend
    process restarts after creating suite rows but before starting a task, those
    PENDING rows have no worker left to advance them.
    """
    db = SessionLocal()
    try:
        task_records = (
            db.query(Task)
            .filter(
                Task.status == "PENDING",
                Task.task_type == "stress",
                Task.batch_id.isnot(None),
                Task.sequence_index.isnot(None),
                Task.start_time.is_(None),
            )
            .order_by(Task.batch_id, Task.server_id, Task.sequence_index)
            .all()
        )
        return _fail_suite_task_records_for_scheduler(
            db,
            task_records,
            "stress suite scheduler recovered orphaned PENDING task after backend restart; recreate the suite",
        )
    finally:
        db.close()


def resume_pending_tasks_after_startup() -> int:
    """Resume PENDING tasks whose in-memory worker was lost by backend restart."""
    db = SessionLocal()
    started = 0
    try:
        pending_tasks = (
            db.query(Task)
            .filter(Task.status == "PENDING")
            .order_by(Task.batch_id.asc().nulls_last(), Task.server_id.asc(), Task.sequence_index.asc().nulls_last(), Task.id.asc())
            .all()
        )
        suite_groups: set[tuple[int, str]] = set()
        for task in pending_tasks:
            if task.task_type == "stress" and task.batch_id and task.sequence_index is not None:
                suite_groups.add((task.server_id, task.batch_id))
                continue
            if task.depends_on_task_id:
                continue
            db.add(TaskLog(task_id=task.task_id, level="SYSTEM", message="startup recovery: pending task worker resumed"))
            _start_task_thread(task.task_id)
            started += 1

        for server_id, batch_id in sorted(suite_groups):
            db.add(TaskLog(task_id=batch_id, level="SYSTEM", message=f"startup recovery: stress suite worker resumed for server {server_id}"))
            thread = threading.Thread(
                target=_run_stress_suite_for_server,
                args=(server_id, batch_id),
                daemon=True,
            )
            thread.start()
            started += 1

        if started:
            db.commit()
        return started
    finally:
        db.close()


def _mark_suite_task_failed(db: Session, task: Task, message: str) -> None:
    task.status = "FAILED"
    task.end_time = datetime.utcnow()
    task.error_message = message[:500]
    db.commit()
    db.add(TaskLog(task_id=task.task_id, level="ERROR", message=message[:1000]))
    db.commit()
    schedule_report_summary_generation(task.task_id)
    try:
        ws_manager.broadcast_status_sync(task.task_id, "FAILED")
        ws_manager.broadcast_done_sync(task.task_id, "FAILED")
    except Exception:
        pass


def _is_suite_task_terminal(db: Session, task_id: str) -> bool:
    status_value = db.query(Task.status).filter(Task.task_id == task_id).scalar()
    return status_value in TERMINAL_TASK_STATUSES


def _wait_for_active_suite_task(db: Session, task: Task) -> bool:
    """Wait for a recovered suite predecessor, then let the scheduler continue."""
    while task.status in UNFINISHED_TASK_STATUSES and task.status != "PENDING":
        sleep(1)
        db.refresh(task)
    return task.status in TERMINAL_TASK_STATUSES


def _run_stress_suite_for_server(server_id: int, batch_id: str, wait_for_lock: bool = False) -> None:
    """Run stress suite tasks sequentially for a single server.

    Tasks are ordered by sequence_index (GPU → CPU/mem → Disk).
    Each task runs in series; failure of one does not stop subsequent tasks.
    Different server threads run in parallel (daemon threads).
    """
    lock = _get_stress_suite_server_lock(server_id)
    acquired = lock.acquire() if wait_for_lock else lock.acquire(timeout=STRESS_SUITE_LOCK_ACQUIRE_TIMEOUT_SECONDS)
    if not acquired:
        db = SessionLocal()
        try:
            _mark_stress_suite_scheduler_blocked(
                db,
                server_id,
                batch_id,
                "stress suite scheduler blocked by previous worker on same server; previous worker did not release lock",
            )
        finally:
            db.close()
        return

    db = SessionLocal()
    try:
        task_records = (
            db.query(Task)
            .filter(Task.batch_id == batch_id, Task.server_id == server_id)
            .order_by(Task.sequence_index)
            .all()
        )

        for task_record in task_records:
            db.refresh(task_record)

            if task_record.status in TERMINAL_TASK_STATUSES:
                continue

            if task_record.status in UNFINISHED_TASK_STATUSES and task_record.status != "PENDING":
                db.add(TaskLog(
                    task_id=task_record.task_id,
                    level="SYSTEM",
                    message=f"stress suite scheduler waiting for recovered active task {task_record.status}",
                ))
                db.commit()
                _wait_for_active_suite_task(db, task_record)
                continue

            if task_record.depends_on_task_id and not _is_suite_task_terminal(db, task_record.depends_on_task_id):
                db.add(TaskLog(
                    task_id=task_record.task_id,
                    level="SYSTEM",
                    message=f"stress suite scheduler waiting for previous task: {task_record.depends_on_task_id}",
                ))
                db.commit()
                break

            try:
                run_task_stage8b(task_record.task_id)
            except Exception:
                pass  # run_task_stage8b handles its own error logging

            db.refresh(task_record)
            if task_record.status not in TERMINAL_TASK_STATUSES:
                _mark_suite_task_failed(
                    db,
                    task_record,
                    f"stress suite task returned before terminal status: {task_record.status}",
                )
                break
    finally:
        db.close()
        lock.release()


@router.post("/stress-suite", response_model=StressSuiteCreateResponse, status_code=status.HTTP_201_CREATED)
def create_stress_suite(
    payload: StressSuiteCreateRequest,
    db: Session = Depends(get_db),
) -> StressSuiteCreateResponse:
    """Create a sequential stress suite: GPU → CPU/mem → Disk on each server.

    Multiple servers execute in parallel (one daemon thread per server),
    but within each server the three stress scripts run sequentially.
    """

    # ── 1. Validate script paths ──
    for sp in payload.script_paths:
        if sp not in STRESS_SUITE_ALLOWED_PATHS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unsupported stress script for suite: {sp}",
            )

    # Filter only the scripts the user selected, preserving suite order
    selected_scripts = [s for s in STRESS_SUITE_SCRIPTS if s["path"] in payload.script_paths]

    # ── 2. Validate params ──
    raw = payload.params

    # Validate forbidden keys
    for key in raw:
        if key in FORBIDDEN_PARAM_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"forbidden param key: {key}",
            )
    has_disk = any(s["name"] == "disk_stress_report.sh" for s in selected_scripts)
    suite_params = validate_stress_suite_params(raw, has_disk=has_disk)

    # ── 3. Deduplicate server_ids ──
    server_ids: list[int] = list(dict.fromkeys(payload.server_ids))

    # ── 4. Generate batch_id ──
    now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand_suffix = token_hex(3)
    batch_id = f"batch-{now_str}-{rand_suffix}"

    # ── 5. Validate servers and create tasks ──
    items: list[StressSuiteCreateItem] = []
    per_server_tasks: dict[int, list[tuple[str, str]]] = {}  # server_id → [(task_id, prev_task_id)]

    for sid in server_ids:
        server = db.get(Server, sid)
        if server is None:
            for s in selected_scripts:
                items.append(StressSuiteCreateItem(
                    server_id=sid, server_name="unknown",
                    script_path=str(s["path"]), task_name=str(s["label"]),
                    status="FAILED",
                ))
            continue

        if server.status != "online":
            for s in selected_scripts:
                items.append(StressSuiteCreateItem(
                    server_id=sid, server_name=server.name,
                    script_path=str(s["path"]), task_name=str(s["label"]),
                    status="SKIPPED",
                ))
            continue

        # Check for unfinished tasks on this server
        running = (
            db.query(Task)
            .filter(Task.server_id == sid, Task.status.in_(UNFINISHED_TASK_STATUSES))
            .first()
        )
        if running is not None:
            for s in selected_scripts:
                items.append(StressSuiteCreateItem(
                    server_id=sid, server_name=server.name,
                    script_path=str(s["path"]), task_name=str(s["label"]),
                    status="SKIPPED",
                ))
            continue

        server_tasks: list[tuple[str, str]] = []
        prev_task_id: str | None = None

        for s in selected_scripts:
            file_record = _get_library_file_or_400(str(s["path"]))
            script_name = str(s["name"])

            remote_work_dir = _build_remote_work_dir("stress")
            command_preview = _build_command_preview(
                task_type="stress",
                file_name=script_name,
                params=suite_params,
                remote_work_dir=remote_work_dir,
            )
            task_id = _generate_task_id()

            task = Task(
                task_id=task_id,
                server_id=sid,
                script_id=None,
                task_type="stress",
                file_path=str(s["path"]),
                file_name=script_name,
                display_category="压测",
                remote_work_dir=remote_work_dir,
                command_preview=command_preview,
                params=suite_params,
                status="PENDING",
                batch_id=batch_id,
                sequence_index=int(s["seq"]),
                depends_on_task_id=prev_task_id,
            )
            db.add(task)
            db.flush()
            db.add(TaskLog(task_id=task_id, level="SYSTEM", message="task created (stress suite)"))
            db.commit()

            items.append(StressSuiteCreateItem(
                server_id=sid, server_name=server.name,
                task_id=task_id, script_path=str(s["path"]),
                task_name=str(s["label"]), status="PENDING",
            ))
            server_tasks.append((task_id, prev_task_id or ""))
            prev_task_id = task_id

        per_server_tasks[sid] = server_tasks

    # ── 6. Start sequential workers per server ──
    for sid in per_server_tasks:
        thread = threading.Thread(
            target=_run_stress_suite_for_server,
            args=(sid, batch_id),
            daemon=True,
        )
        thread.start()

    # ── 7. Audit log ──
    script_names = [str(s["label"]) for s in selected_scripts]
    write_audit_log(
        db, action="task.stress_suite_create", target_type="task", status="success",
        actor="visitor",
        target_id=batch_id,
        target_name=", ".join(script_names),
        task_id=batch_id,
        message=f"stress suite created: {', '.join(script_names)} on {len(per_server_tasks)} servers",
        detail={"batch_id": batch_id, "server_ids": server_ids,
                "scripts": [str(s["path"]) for s in selected_scripts],
                "total_tasks": len(items), "server_count": len(per_server_tasks)},
    )

    return StressSuiteCreateResponse(
        batch_id=batch_id,
        total=len(items),
        items=items,
    )


RETRYABLE_BATCH_TASK_STATUSES = {"FAILED", "CANCELED", "TIMEOUT"}


def _batch_task_can_retry(task: Task, db: Session) -> bool:
    status_value = (task.status or "").upper()
    if status_value in RETRYABLE_BATCH_TASK_STATUSES:
        return True
    summary = get_cached_report_summary(db, task.task_id)
    return bool(summary and (summary.report_status or "").upper() == "FAIL")


@router.post("/{task_id}/retry-in-batch", response_model=BatchTaskRetryResponse, status_code=status.HTTP_201_CREATED)
def retry_batch_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> BatchTaskRetryResponse:
    """Append a retry task to the same stress-suite batch and server queue."""
    original = _get_task_or_404(db, task_id)
    if not original.batch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is not part of a batch")
    if original.task_type != "stress":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only stress suite task retry is supported")
    if not original.file_path or original.file_path not in STRESS_SUITE_ALLOWED_PATHS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task script is not retryable")
    if not _batch_task_can_retry(original, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="task is not failed or canceled")

    server = db.get(Server, original.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="server_id not found")
    if server.status != "online":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="server is not online")
    other_unfinished = (
        db.query(Task)
        .filter(
            Task.server_id == original.server_id,
            Task.status.in_(UNFINISHED_TASK_STATUSES),
            (Task.batch_id != original.batch_id) | (Task.batch_id.is_(None)),
        )
        .first()
    )
    if other_unfinished is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="server has unfinished task outside this batch")
    existing_retry = (
        db.query(Task)
        .filter(
            Task.batch_id == original.batch_id,
            Task.server_id == original.server_id,
            Task.status.in_(UNFINISHED_TASK_STATUSES),
            Task.params["__retry_of_task_id"].as_string() == original.task_id,
        )
        .first()
    )
    if existing_retry is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="retry task already queued or running")

    file_record = _get_library_file_or_400(original.file_path)
    same_server_tasks = (
        db.query(Task)
        .filter(Task.batch_id == original.batch_id, Task.server_id == original.server_id)
        .order_by(Task.sequence_index.asc().nulls_last(), Task.id.asc())
        .all()
    )
    max_sequence = max((task.sequence_index or 0) for task in same_server_tasks) if same_server_tasks else 0
    last_task = same_server_tasks[-1] if same_server_tasks else None
    retry_sequence = max_sequence + 1
    retry_task_id = _generate_task_id()
    retry_params = dict(original.params or {})
    retry_params["__retry_of_task_id"] = original.task_id
    retry_params["__retry_created_at"] = datetime.utcnow().isoformat(timespec="seconds")
    remote_work_dir = _build_remote_work_dir("stress")
    command_preview = _build_command_preview(
        task_type="stress",
        file_name=str(file_record["name"]),
        params=retry_params,
        remote_work_dir=remote_work_dir,
    )

    retry_task = Task(
        task_id=retry_task_id,
        server_id=original.server_id,
        script_id=None,
        task_type="stress",
        file_path=str(file_record["path"]),
        file_name=str(file_record["name"]),
        display_category=original.display_category or "压测",
        remote_work_dir=remote_work_dir,
        command_preview=command_preview,
        params=retry_params,
        status="PENDING",
        batch_id=original.batch_id,
        sequence_index=retry_sequence,
        depends_on_task_id=last_task.task_id if last_task else None,
    )
    db.add(retry_task)
    db.flush()
    db.add(TaskLog(
        task_id=retry_task_id,
        level="SYSTEM",
        message=f"retry task created in batch {original.batch_id}; original={original.task_id}",
    ))
    db.commit()

    write_audit_log(
        db,
        action="task.batch_retry",
        target_type="task",
        status="success",
        actor="visitor",
        target_id=retry_task_id,
        target_name=f"{server.name} · {retry_task.file_name}",
        server_id=server.id,
        server_name=server.name,
        task_id=retry_task_id,
        message=f"retry task {original.task_id} as {retry_task_id}",
        detail={
            "batch_id": original.batch_id,
            "original_task_id": original.task_id,
            "retry_task_id": retry_task_id,
            "sequence_index": retry_sequence,
            "depends_on_task_id": retry_task.depends_on_task_id,
        },
    )

    thread = threading.Thread(
        target=_run_stress_suite_for_server,
        args=(original.server_id, original.batch_id, True),
        daemon=True,
    )
    thread.start()

    return BatchTaskRetryResponse(
        original_task_id=original.task_id,
        retry_task_id=retry_task_id,
        batch_id=original.batch_id,
        server_id=original.server_id,
        sequence_index=retry_sequence,
        depends_on_task_id=retry_task.depends_on_task_id,
        status="PENDING",
    )


# ── Batch summary / detail (Phase 26A) ──

VALID_BATCH_STATUS_VALUES = {"RUNNING", "SUCCESS", "FAILED", "PARTIAL_FAILED", "CANCELED", "PARTIAL_CANCELED"}
BATCH_CANCELABLE_STATUSES = set(CANCELABLE_TASK_STATUSES) | {"QUEUED", "CREATED"}
BATCH_PLATFORM_ONLY_CANCEL_STATUSES = BATCH_CANCELABLE_STATUSES - {"RUNNING"}
BATCH_TERMINAL_STATUSES = set(TERMINAL_TASK_STATUSES) | {"TIMEOUT"}
BATCH_UNFINISHED_STATUSES = BATCH_CANCELABLE_STATUSES | {"CANCELING"}
BATCH_PENDING_STATUSES = {"PENDING", "QUEUED", "CREATED"}
BATCH_FAILED_STATUSES = {"FAILED", "TIMEOUT"}
BATCH_CANCELED_STATUSES = {"CANCELED", "CANCELLED"}


def _latest_batch_attempts(tasks: list[Task]) -> list[Task]:
    """Return the latest attempt for every original task in a batch.

    Retry tasks link to the attempt they replace through
    ``params.__retry_of_task_id``.  Older attempts remain queryable, but do
    not keep a batch in FAILED after a later retry succeeds.
    """
    by_task_id = {task.task_id: task for task in tasks}

    def _root_task_id(task: Task) -> str:
        current = task
        visited: set[str] = set()
        while current.task_id not in visited:
            visited.add(current.task_id)
            params = current.params if isinstance(current.params, dict) else {}
            retry_of = params.get("__retry_of_task_id")
            if not isinstance(retry_of, str) or retry_of not in by_task_id:
                break
            current = by_task_id[retry_of]
        return current.task_id

    latest_by_root: dict[str, Task] = {}
    for task in tasks:
        root_task_id = _root_task_id(task)
        previous = latest_by_root.get(root_task_id)
        if previous is None or (task.sequence_index or 0, task.id) > (previous.sequence_index or 0, previous.id):
            latest_by_root[root_task_id] = task
    return list(latest_by_root.values())


def _compute_batch_status(tasks: list[Task], db: Session | None = None) -> str:
    """Derive the aggregate batch status from its child tasks.

    Uses final_status (considering report) where available, falling back
    to execution status for tasks without report summary.
    """
    # A retry supersedes its original attempt for the batch's current outcome.
    # The original task remains in the batch for audit/history purposes.
    effective_tasks = _latest_batch_attempts(tasks)

    # Batch-load report summaries for the effective child tasks
    task_ids = [t.task_id for t in effective_tasks]
    report_map: dict[str, str] = {}
    if task_ids:
        try:
            from app.models.task import TaskReportSummary
            _sess: Session = db if db is not None else SessionLocal()
            cache_rows = (
                _sess.query(TaskReportSummary.task_id, TaskReportSummary.report_status)
                .filter(TaskReportSummary.task_id.in_(task_ids))
                .all()
            )
            for tid, rs in cache_rows:
                report_map[tid] = rs
            if db is None:
                _sess.close()
        except Exception:
            pass

    def _child_final(t: Task) -> str:
        report_status = report_map.get(t.task_id, "UNKNOWN").upper()
        return resolve_final_status(t.status or "UNKNOWN", report_status)

    # Collect final statuses for all children
    final_set = {_child_final(t) for t in effective_tasks}

    # Map final statuses back to batch-status concepts
    # Note: resolve_final_status maps report "FAIL" → "FAILED", report "PASS" → "SUCCESS"
    has_failed = "FAILED" in final_set
    has_pass = "SUCCESS" in final_set
    has_unknown = "UNKNOWN" in final_set
    exec_statuses = {t.status for t in effective_tasks}

    # Any still-non-terminal execution status → batch still running
    if exec_statuses & BATCH_UNFINISHED_STATUSES:
        return "RUNNING"
    # FAILED (includes both report FAIL and execution FAILED)
    if has_failed:
        if has_pass:
            return "PARTIAL_FAILED"
        return "FAILED"
    # All PASS
    if has_pass and not has_unknown:
        return "SUCCESS"
    # Some stress reports (for example disk) may not yield a PASS/FAIL summary
    # even though the platform task completed successfully.
    if exec_statuses == {"SUCCESS"}:
        return "SUCCESS"
    # Cancel scenarios
    if exec_statuses == {"CANCELED"}:
        return "CANCELED"
    if "CANCELED" in exec_statuses and "SUCCESS" not in exec_statuses and "FAILED" not in exec_statuses:
        return "CANCELED"
    if "CANCELED" in exec_statuses:
        return "PARTIAL_CANCELED"
    # Fallback
    if "FAILED" in exec_statuses:
        return "PARTIAL_FAILED"
    return "RUNNING"


@router.get("/batches", response_model=BatchSummaryListResponse)
def list_batches(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None, min_length=1),
) -> BatchSummaryListResponse:
    """List all batch groups with aggregate summaries."""
    # Subquery: group tasks by batch_id (non-null only)
    batch_query = (
        db.query(
            Task.batch_id,
            func.min(Task.task_type).label("task_type"),
            func.min(Task.created_at).label("created_at"),
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == "SUCCESS", 1), else_=0)).label("success"),
            func.sum(case((Task.status.in_(BATCH_FAILED_STATUSES), 1), else_=0)).label("failed"),
            func.sum(case((Task.status == "RUNNING", 1), else_=0)).label("running"),
            func.sum(case((Task.status.in_(BATCH_PENDING_STATUSES), 1), else_=0)).label("pending"),
            func.sum(case((Task.status.in_(BATCH_CANCELED_STATUSES), 1), else_=0)).label("canceled"),
        )
        .filter(Task.batch_id.isnot(None))
        .filter(Task.hidden_from_history == 0)
    )

    if keyword is not None:
        like_pattern = f"%{keyword}%"
        batch_query = batch_query.outerjoin(Server, Task.server_id == Server.id).filter(
            or_(
                Task.batch_id.ilike(like_pattern),
                Task.file_name.ilike(like_pattern),
                Task.file_path.ilike(like_pattern),
                Server.name.ilike(like_pattern),
                Server.host.ilike(like_pattern),
            )
        )

    subq = batch_query.group_by(Task.batch_id).subquery()

    # Build main query from subquery
    q = db.query(subq)

    if status is not None:
        # We need to filter by computed status — re-derive in SQL is complex;
        # instead filter after fetching. Limit pre-fetch.
        pass

    total_q = q.count()
    items_q = q.order_by(subq.c.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items: list[BatchSummaryItem] = []
    for row in items_q:
        # Fetch server names and distinct script names for this batch
        child_tasks = (
            db.query(Task)
            .filter(Task.batch_id == row.batch_id, Task.hidden_from_history == 0)
            .all()
        )
        server_names: list[str] = []
        script_names: set[str] = set()
        for t in child_tasks:
            srv = db.get(Server, t.server_id)
            if srv:
                if srv.name not in server_names:
                    server_names.append(srv.name)
            if t.file_name:
                script_names.add(t.file_name)

        raw_status = _compute_batch_status(child_tasks, db)

        # Extract stress test duration from child task params
        stress_duration: int | None = None
        for t in child_tasks:
            if t.params and isinstance(t.params, dict) and t.params.get("duration_seconds") is not None:
                try:
                    dur = int(t.params["duration_seconds"])
                    if stress_duration is None or dur > stress_duration:
                        stress_duration = dur
                except (ValueError, TypeError):
                    pass

        # Apply status filter post-query
        if status is not None and raw_status != status:
            continue

        items.append(BatchSummaryItem(
            batch_id=row.batch_id,
            task_type=row.task_type,
            script_names=sorted(script_names),
            created_at=row.created_at,
            total=row.total or 0,
            success=row.success or 0,
            failed=row.failed or 0,
            running=row.running or 0,
            pending=row.pending or 0,
            canceled=row.canceled or 0,
            status=raw_status,
            servers=server_names,
            stress_duration_seconds=stress_duration,
        ))

    return BatchSummaryListResponse(
        items=items,
        total=len(items) + total_q - len(items_q),  # approx if filtered
        page=page,
        page_size=page_size,
    )


def _cancel_running_task_for_batch(db: Session, task: Task) -> tuple[str, bool]:
    """Best-effort remote stop for a running task, then always finalize platform state."""
    task_id = task.task_id
    task.status = "CANCELING"
    db.commit()
    _add_task_log(db, task_id, "SYSTEM", "batch cancel requested")

    server = db.get(Server, task.server_id)
    executor = SSHExecutor(timeout=MONITOR_TIMEOUT_SECONDS)
    remote_unreachable = False
    remote_process_not_confirmed = False
    cancel_error_detail: str | None = None
    try:
        if server is None:
            remote_unreachable = True
            cancel_error_detail = "canceled by batch cancel, remote server unreachable, remote process not confirmed: server not found"
            _add_task_log(db, task_id, "WARN", "batch cancel: server not found, remote process not confirmed")
        else:
            try:
                executor.connect(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    key_path=server.key_path,
                )
            except SSHExecutorError as exc:
                remote_unreachable = True
                cancel_error_detail = f"canceled by batch cancel, remote server unreachable, remote process not confirmed: {exc}"
                _add_task_log(db, task_id, "WARN", f"batch cancel: SSH unreachable, remote process not confirmed: {exc}")
            else:
                try:
                    _cancel_remote_process(executor, task, db)
                except SSHExecutorError as exc:
                    remote_process_not_confirmed = True
                    cancel_error_detail = f"canceled by batch cancel, remote process not confirmed: {exc}"
                    _add_task_log(db, task_id, "WARN", f"batch cancel: remote process not confirmed: {exc}")

        db.refresh(task)
        if task.status == "CANCELING":
            _mark_task_canceled(
                db,
                task,
                error_message=cancel_error_detail or "canceled by batch cancel",
                log_message="task canceled by batch cancel",
            )
            if remote_unreachable:
                return "platform canceled, remote unreachable, process not confirmed", True
            if remote_process_not_confirmed:
                return "platform canceled, remote process not confirmed", True
            return "canceled", True

        if task.status == "CANCELED":
            return "canceled", True
        return f"skipped, task already finalized as {task.status}", False
    finally:
        executor.close()


def _best_effort_cancel_remote_process(db: Session, task: Task) -> None:
    """Attempt to kill the remote process of a FAILED/CANCELED task.
    This is best-effort — never raises. Only used during batch cancel
    where the task is already terminal but the remote process might still
    be running (e.g. backend restart mid-execution).
    """
    task_id = task.task_id
    if not task.remote_work_dir:
        return
    server = db.get(Server, task.server_id)
    if server is None:
        return
    executor = SSHExecutor(timeout=MONITOR_TIMEOUT_SECONDS)
    try:
        try:
            executor.connect(
                host=server.host,
                port=server.port,
                username=server.username,
                key_path=server.key_path,
            )
        except SSHExecutorError:
            _add_task_log(db, task_id, "WARN", "batch cancel: remote cleanup skipped (SSH unreachable)")
            return
        _cancel_remote_process(executor, task, db)
        _add_task_log(db, task_id, "SYSTEM", "batch cancel: remote process cleanup attempted (best-effort)")
    except Exception:
        pass
    finally:
        executor.close()


@router.post("/batches/{batch_id}/cancel", response_model=BatchCancelResponse)
def cancel_batch(
    batch_id: str,
    payload: BatchCancelRequest = BatchCancelRequest(),
    db: Session = Depends(get_db),
) -> BatchCancelResponse:
    """Cancel every unfinished task in a batch without deleting remote directories."""
    if payload.delete_remote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delete_remote is not supported for batch cancel",
        )

    tasks = (
        db.query(Task)
        .filter(Task.batch_id == batch_id)
        .order_by(Task.server_id.asc(), Task.sequence_index.asc().nulls_last(), Task.id.asc())
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")

    items: list[BatchCancelItem] = []
    canceled = skipped = failed = 0

    for task in tasks:
        old_status = task.status
        try:
            # ── Terminal tasks (SUCCESS / FAILED / CANCELED / TIMEOUT) ──
            # We still try to kill the remote process: the task might have
            # FAILED on the platform while the remote stress-ng keeps running
            # (e.g. backend restart mid-execution, SSH flash disconnect).
            if old_status in BATCH_TERMINAL_STATUSES:
                if old_status in ("FAILED", "TIMEOUT", "CANCELED"):
                    _best_effort_cancel_remote_process(db, task)
                skipped += 1
                items.append(BatchCancelItem(
                    task_id=task.task_id,
                    old_status=old_status,
                    new_status=task.status,
                    message="skipped, task already terminal (remote cleanup attempted)",
                ))
                continue

            if old_status == "RUNNING":
                message, did_cancel = _cancel_running_task_for_batch(db, task)
                db.refresh(task)
                if did_cancel:
                    canceled += 1
                else:
                    skipped += 1
                items.append(BatchCancelItem(
                    task_id=task.task_id,
                    old_status=old_status,
                    new_status=task.status,
                    message=message,
                ))
                continue

            if old_status in BATCH_PLATFORM_ONLY_CANCEL_STATUSES or old_status == "CANCELING":
                _add_task_log(db, task.task_id, "SYSTEM", "batch cancel requested")
                _mark_task_canceled(
                    db,
                    task,
                    error_message="canceled by batch cancel before start",
                    log_message="task canceled by batch cancel before start",
                )
                canceled += 1
                items.append(BatchCancelItem(
                    task_id=task.task_id,
                    old_status=old_status,
                    new_status=task.status,
                    message="canceled",
                ))
                continue

            skipped += 1
            items.append(BatchCancelItem(
                task_id=task.task_id,
                old_status=old_status,
                new_status=task.status,
                message="skipped, task status is not cancelable",
            ))
        except Exception as exc:
            failed += 1
            db.rollback()
            db.refresh(task)
            items.append(BatchCancelItem(
                task_id=task.task_id,
                old_status=old_status,
                new_status=task.status,
                message=f"failed: {type(exc).__name__}: {exc}",
            ))

    write_audit_log(
        db, action="task.batch_cancel", target_type="task", status="success" if failed == 0 else "failed",
        actor="visitor",
        target_id=batch_id,
        task_id=batch_id,
        message=f"batch {batch_id} cancel: {canceled} canceled, {skipped} skipped, {failed} failed",
        detail={"batch_id": batch_id, "total": len(tasks), "canceled": canceled, "skipped": skipped, "failed": failed},
    )

    return BatchCancelResponse(
        batch_id=batch_id,
        total=len(tasks),
        canceled=canceled,
        skipped=skipped,
        failed=failed,
        items=items,
    )


@router.get("/batches/{batch_id}", response_model=BatchDetailResponse)
def get_batch_detail(
    batch_id: str,
    db: Session = Depends(get_db),
) -> BatchDetailResponse:
    """Get detailed task list for a single batch."""
    tasks = (
        db.query(Task)
        .outerjoin(Server, Task.server_id == Server.id)
        .filter(Task.batch_id == batch_id, Task.hidden_from_history == 0)
        .order_by(Server.name.asc().nulls_last(), Task.sequence_index.asc().nulls_last(), Task.id.asc())
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")

    # Build summary
    # Batch-load report summaries for final_status computation
    report_map: dict[str, str] = {}
    report_summary_map: dict[str, TaskReportSummary] = {}
    try:
        from app.models.task import TaskReportSummary
        cache_rows = (
            db.query(TaskReportSummary)
            .filter(TaskReportSummary.task_id.in_([t.task_id for t in tasks]))
            .all()
        )
        for row in cache_rows:
            report_map[row.task_id] = row.report_status
            report_summary_map[row.task_id] = row
    except Exception:
        pass

    server_names: list[str] = []
    detail_items: list[BatchTaskDetailItem] = []
    total = len(tasks)
    success = failed = running = pending = canceled = 0
    for t in tasks:
        srv = db.get(Server, t.server_id)
        srv_name = srv.name if srv else "unknown"
        srv_host = srv.host if srv else ""
        srv_username = srv.username if srv else None

        if srv and srv.name not in server_names:
            server_names.append(srv.name)

        # Compute final_status
        child_report = report_map.get(t.task_id, "UNKNOWN").upper()
        child_final = resolve_final_status(t.status or "UNKNOWN", child_report)

        # Count statuses (using final_status for accuracy)
        status_value = (t.status or "").upper()
        if child_final == "SUCCESS" or (child_final == "UNKNOWN" and status_value == "SUCCESS"):
            success += 1
        elif child_final in ("FAIL", "FAILED") or status_value in BATCH_FAILED_STATUSES:
            failed += 1
        elif status_value == "RUNNING":
            running += 1
        elif status_value in BATCH_PENDING_STATUSES:
            pending += 1
        elif status_value in BATCH_CANCELED_STATUSES:
            canceled += 1

        artifact_dir = ARTIFACTS_DIR / t.task_id
        has_artifacts = artifact_dir.is_dir() and any(entry.is_file() for entry in artifact_dir.iterdir())

        # 计算耗时（秒）
        _dur: int | None = None
        if t.start_time and t.end_time:
            _delta = t.end_time - t.start_time
            _dur = int(_delta.total_seconds())

        task_name = f"{srv_name} · {t.task_type or 'task'} · {t.file_name or 'unknown'}"

        report_summary = report_summary_map.get(t.task_id)
        detail_items.append(BatchTaskDetailItem(
            task_id=t.task_id,
            task_name=task_name,
            server_id=t.server_id,
            server_name=srv_name,
            host=srv_host,
            username=srv_username,
            status=t.status,
            final_status=child_final,
            report_status=child_report,
            sequence_index=t.sequence_index,
            created_at=t.created_at,
            started_at=t.start_time,
            ended_at=t.end_time,
            duration_seconds=_dur,
            remote_work_dir=t.remote_work_dir,
            has_artifacts=has_artifacts,
            error_summary=t.error_message,
            failure_reason=report_summary.failure_reason if report_summary else None,
            params=t.params,
        ))

    batch_status = _compute_batch_status(tasks, db)

    # Collect distinct script names
    script_names: set[str] = set()
    for t in tasks:
        if t.file_name:
            script_names.add(t.file_name)

    # Extract stress test duration from child task params
    stress_duration: int | None = None
    for t in tasks:
        if t.params and isinstance(t.params, dict) and t.params.get("duration_seconds") is not None:
            try:
                dur = int(t.params["duration_seconds"])
                if stress_duration is None or dur > stress_duration:
                    stress_duration = dur
            except (ValueError, TypeError):
                pass

    summary = BatchSummaryItem(
        batch_id=batch_id,
        task_type=tasks[0].task_type if tasks else None,
        script_names=sorted(script_names),
        created_at=tasks[0].created_at if tasks else datetime.now(),
        total=total,
        success=success,
        failed=failed,
        running=running,
        pending=pending,
        canceled=canceled,
        status=batch_status,
        servers=server_names,
        stress_duration_seconds=stress_duration,
    )

    return BatchDetailResponse(
        batch_id=batch_id,
        summary=summary,
        tasks=detail_items,
    )


def _iter_download_file(path: Path):
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            yield chunk


def _cleanup_download_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


@router.get("/batches/{batch_id}/report/download-zip")
def download_batch_report_zip_compat(
    batch_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    exported = export_batch_report_zip(db, batch_id)
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(exported.filename)}",
    }
    return StreamingResponse(
        _iter_download_file(exported.path),
        media_type="application/zip",
        headers=headers,
        background=BackgroundTask(_cleanup_download_file, exported.path),
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    task = _get_task_or_404(db, task_id)
    return _serialize_task(task, db)


@router.get("/{task_id}/logs", response_model=list[TaskLogRead])
def list_task_logs(task_id: str, db: Session = Depends(get_db)) -> list[TaskLog]:
    _get_task_or_404(db, task_id)
    return (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.id.asc())
        .all()
    )


@router.get("/{task_id}/logs/download")
def download_task_logs(task_id: str, db: Session = Depends(get_db)) -> Response:
    _get_task_or_404(db, task_id)
    logs = (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.id.asc())
        .all()
    )

    if not logs:
        content = "no logs found\n"
    else:
        lines = []
        for log in logs:
            ts = log.created_at.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{ts}] [{log.level}] {log.message}")
        content = "\n".join(lines) + "\n"

    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{task_id}.log"'
        },
    )


@router.websocket("/{task_id}/logs/ws")
async def task_logs_websocket(ws: WebSocket, task_id: str) -> None:
    """WebSocket endpoint for real-time task log streaming."""
    # Validate task exists (use a short-lived session)
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None:
            await ws.accept()
            await ws.send_json({"type": "error", "message": "task not found"})
            await ws.close()
            return
    finally:
        db.close()

    await ws_manager.connect(task_id, ws)

    last_log_id = 0
    last_status = task.status

    try:
        # Send existing logs
        db = SessionLocal()
        try:
            existing = (
                db.query(TaskLog)
                .filter(TaskLog.task_id == task_id)
                .order_by(TaskLog.id.asc())
                .all()
            )
            for log in existing:
                await ws.send_json({
                    "type": "log",
                    "task_id": task_id,
                    "level": log.level,
                    "line": log.message,
                    "created_at": str(log.created_at) if log.created_at else None,
                })
                last_log_id = max(last_log_id, log.id)
        finally:
            db.close()

        # Send current status
        await ws.send_json({
            "type": "status",
            "task_id": task_id,
            "status": last_status,
        })

        # Keep connection alive, handle incoming pings, and tail DB-backed updates.
        # The DB tail keeps WebSocket usable when uvicorn has multiple workers:
        # task logs may be written by one worker while the browser is connected to another.
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=WS_DB_POLL_INTERVAL_SECONDS)
                # Client sent a message — ignore (could be ping/pong)
                continue
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            db = SessionLocal()
            try:
                new_logs = (
                    db.query(TaskLog)
                    .filter(TaskLog.task_id == task_id, TaskLog.id > last_log_id)
                    .order_by(TaskLog.id.asc())
                    .all()
                )
                for log in new_logs:
                    await ws.send_json({
                        "type": "log",
                        "task_id": task_id,
                        "level": log.level,
                        "line": log.message,
                        "created_at": str(log.created_at) if log.created_at else None,
                    })
                    last_log_id = max(last_log_id, log.id)

                current_status = (
                    db.query(Task.status)
                    .filter(Task.task_id == task_id)
                    .scalar()
                )
                if current_status and current_status != last_status:
                    last_status = current_status
                    await ws.send_json({
                        "type": "status",
                        "task_id": task_id,
                        "status": current_status,
                    })
                    if current_status in TERMINAL_TASK_STATUSES:
                        await ws.send_json({
                            "type": "done",
                            "task_id": task_id,
                            "status": current_status,
                        })
            finally:
                db.close()
    except Exception:
        pass
    finally:
        ws_manager.disconnect(task_id, ws)


@router.get("/{task_id}/diagnosis", response_model=TaskDiagnosisResponse)
def diagnose_task(task_id: str, db: Session = Depends(get_db)) -> TaskDiagnosisResponse:
    """Return cached diagnosis summary. This endpoint must not do SSH or file IO."""
    task = _get_task_or_404(db, task_id)

    host = db.query(Server).with_entities(Server.host).filter(Server.id == task.server_id).scalar() or "?"
    task_name = f"{host} · {task.file_name or task.task_type} · {task.task_id}"
    cache = get_cached_report_summary(db, task_id)
    summary_json = cache.summary_json if cache and isinstance(cache.summary_json, dict) else unknown_report_summary(task)
    diagnosis = summary_json.get("diagnosis")
    if not isinstance(diagnosis, dict):
        diagnosis = unknown_report_summary(task)["diagnosis"]

    # Audit log (best-effort, must not affect response)
    try:
        write_audit_log(
            db, action="task.diagnose", target_type="task", status="success",
            target_id=task_id, target_name=task_name,
            task_id=task_id, server_id=task.server_id,
            message=f"diagnose task {task_id}: {diagnosis.get('category', 'unknown')}",
            detail={"category": diagnosis.get("category"), "attribution": diagnosis.get("attribution"),
                    "level": diagnosis.get("level"), "file_name": task.file_name,
                    "task_status": task.status, "cache_hit": cache is not None},
        )
    except Exception:
        pass

    # --- resolve final_status ---
    execution_status = task.status or "UNKNOWN"
    report_status = (summary_json.get("report_status") or "UNKNOWN").upper()
    final_status = resolve_final_status(execution_status, report_status)

    return TaskDiagnosisResponse(
        task_id=task.task_id,
        task_name=task_name,
        status=task.status,
        execution_status=execution_status,
        report_status=report_status,
        final_status=final_status,
        diagnosis=diagnosis,
    )


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
def cancel_task(
    task_id: str,
    payload: TaskCancelRequest = TaskCancelRequest(),
    db: Session = Depends(get_db),
) -> TaskCancelResponse:
    task = _get_task_or_404(db, task_id)
    if task.status in TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task already completed")
    if task.status == "CANCELING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="task is already canceling")
    if task.status not in CANCELABLE_TASK_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is not cancelable")

    # PENDING / CONNECTING / PREPARING / UPLOADING are platform-only cancel states:
    # they have not started a remote process yet, so no SSH dependency is needed.
    if task.status != "RUNNING":
        _add_task_log(db, task_id, "SYSTEM", "cancel requested by user")
        _mark_task_canceled(
            db,
            task,
            error_message="canceled before start",
            log_message="task canceled before start",
        )
        _cancel_following_batch_tasks(db, task, reason="canceled because previous batch task was canceled")
        write_audit_log(
            db, action="task.cancel", target_type="task", status="success",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"task {task_id} canceled before start",
            detail={"server_id": task.server_id, "delete_remote_files": False, "platform_only": True},
        )
        return TaskCancelResponse(
            task_id=task.task_id,
            status=task.status,
            message="任务已在平台标记为已取消，未尝试远端 SSH。",
        )

    task.status = "CANCELING"
    db.commit()
    _add_task_log(db, task_id, "SYSTEM", "cancel requested by user")

    server = _get_server_or_400(db, task.server_id)
    executor = SSHExecutor(timeout=MONITOR_TIMEOUT_SECONDS)
    remote_unreachable = False
    remote_process_not_confirmed = False
    cancel_error_detail: str | None = None
    try:
        try:
            executor.connect(
                host=server.host,
                port=server.port,
                username=server.username,
                key_path=server.key_path,
            )
        except SSHExecutorError as exc:
            remote_unreachable = True
            cancel_error_detail = f"canceled by user, remote server unreachable, remote process not confirmed: {exc}"
            _add_task_log(db, task_id, "WARN", f"cancel: SSH unreachable, remote process not confirmed: {exc}")
        else:
            # Phase 1: Terminate remote process (best effort — never fail cancel)
            try:
                _cancel_remote_process(executor, task, db)
            except SSHExecutorError as exc:
                remote_process_not_confirmed = True
                cancel_error_detail = f"canceled by user, remote process not confirmed: {exc}"
                _add_task_log(db, task_id, "WARN", f"cancel: remote process not confirmed: {exc}")

        # Phase 2: Mark canceled regardless of remote connectivity
        db.refresh(task)
        if task.status == "CANCELING":
            _mark_task_canceled(
                db,
                task,
                error_message=cancel_error_detail or "canceled by user",
                log_message="task canceled",
            )
        else:
            # Another worker might have finalized it while we were best-effort stopping remote work.
            _add_task_log(db, task_id, "SYSTEM", f"cancel: task already finalized as {task.status}")

        if remote_unreachable:
            _add_task_log(db, task_id, "SYSTEM", "cancel: remote unreachable, skip artifact collection and temp cleanup")
        else:
            # Phase 3: Best-effort artifact collection
            _add_task_log(db, task_id, "SYSTEM", "cancel: artifact collection best-effort")
            try:
                from app.core.artifact_collector import collect_artifacts
                collect_artifacts(db, task_id, task.remote_work_dir, executor)
            except Exception as exc:
                _add_task_log(db, task_id, "WARN", f"cancel: artifact collection skipped: {exc}")
                _add_task_log(db, task_id, "SYSTEM", "cancel: artifact collection skipped (best effort)")

            # Phase 4: Cleanup temp download dirs for known whitelist scripts (best effort)
            _cleanup_temp_dirs(executor, task, db)

        _cancel_following_batch_tasks(db, task, reason="canceled because previous batch task was canceled")

        if task.status == "CANCELED":
            if remote_unreachable:
                response_message = "任务已在平台标记为已取消。服务器当前不可达，远端进程是否仍在运行无法确认。"
            elif remote_process_not_confirmed:
                response_message = "任务已在平台标记为已取消。远端进程是否已终止无法确认。"
            else:
                response_message = "任务已在平台标记为已取消。"
        else:
            response_message = f"任务状态已更新为 {task.status}。"

        write_audit_log(
            db, action="task.cancel", target_type="task", status="success",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"task {task_id} canceled",
            detail={
                "server_id": task.server_id,
                "delete_remote_files": False,
                "remote_unreachable": remote_unreachable,
                "remote_process_not_confirmed": remote_process_not_confirmed,
            },
        )
        return TaskCancelResponse(task_id=task.task_id, status=task.status, message=response_message)
    except SSHExecutorError as exc:
        # This branch should no longer be hit for SSH failures, but keep it as a final safety net.
        db.refresh(task)
        if task.status == "CANCELING":
            _mark_task_canceled(
                db,
                task,
                error_message=f"canceled by user, remote server unreachable, remote process not confirmed: {exc}",
                log_message="task canceled",
            )
        _cancel_following_batch_tasks(db, task, reason="canceled because previous batch task was canceled")
        _add_task_log(db, task_id, "WARN", f"cancel: fallback finalization after SSH error: {exc}")
        if remote_unreachable:
            message = "任务已在平台标记为已取消。服务器当前不可达，远端进程是否仍在运行无法确认。"
        elif remote_process_not_confirmed:
            message = "任务已在平台标记为已取消。远端进程是否已终止无法确认。"
        else:
            message = "任务已在平台标记为已取消。"
        write_audit_log(
            db, action="task.cancel", target_type="task", status="success",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"task {task_id} canceled after SSH error",
            detail={"error": str(exc), "server_id": task.server_id, "delete_remote_files": False},
        )
        return TaskCancelResponse(
            task_id=task.task_id,
            status=task.status,
            message=message,
        )
    finally:
        executor.close()


@router.post("/{task_id}/cleanup", response_model=TaskCleanupResponse)
def cleanup_task(task_id: str, db: Session = Depends(get_db)) -> TaskCleanupResponse:
    task = _get_task_or_404(db, task_id)

    if task.status not in TERMINAL_TASK_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"task is not completed (current status: {task.status})",
        )

    _add_task_log(db, task_id, "SYSTEM", "cleanup requested by user")
    messages: list[str] = []

    local_artifacts_removed = _cleanup_local_artifacts(task_id, messages, db)

    remote_work_dir_removed = False
    if task.remote_work_dir and task.task_type != "apptainer":
        if not _is_safe_remote_work_dir(task.remote_work_dir):
            msg = f"remote cleanup refused: unsafe remote_work_dir {task.remote_work_dir}"
            messages.append(msg)
            _add_task_log(db, task_id, "ERROR", msg)
        else:
            server = _get_server_or_400(db, task.server_id)
            executor = SSHExecutor(timeout=CLEANUP_TIMEOUT_SECONDS)
            try:
                executor.connect(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    key_path=server.key_path,
                )
                remote_work_dir_removed = _perform_remote_work_dir_cleanup(executor, task, messages, db)
            except SSHExecutorError as exc:
                msg = f"remote cleanup failed: SSH connection error: {exc}"
                messages.append(msg)
                _add_task_log(db, task_id, "ERROR", msg)
            finally:
                executor.close()
    elif not task.remote_work_dir:
        msg = "remote cleanup skipped: remote_work_dir is empty"
        messages.append(msg)
        _add_task_log(db, task_id, "SYSTEM", msg)
    else:
        msg = "remote cleanup skipped: apptainer task"
        messages.append(msg)
        _add_task_log(db, task_id, "SYSTEM", msg)

    _add_task_log(db, task_id, "SYSTEM", "cleanup completed")
    return TaskCleanupResponse(
        task_id=task.task_id,
        local_artifacts_removed=local_artifacts_removed,
        remote_work_dir_removed=remote_work_dir_removed,
        messages=messages,
    )


@router.delete("/{task_id}", response_model=TaskDeleteResponse)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> TaskDeleteResponse:
    task = _get_task_or_404(db, task_id)
    _task_type = task.task_type
    _task_status = task.status

    if _task_status not in TERMINAL_TASK_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"task is not completed (current status: {task.status})",
        )

    messages: list[str] = []

    # 1. Clean local artifacts (best effort, continue on not-found)
    local_artifacts_removed = _delete_local_artifacts(task_id, messages)

    # 2. Clean remote work dir (fail hard on safety/SSH error)
    remote_work_dir_removed = False
    if task.remote_work_dir and task.task_type != "apptainer":
        if not _is_safe_remote_work_dir(task.remote_work_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unsafe remote_work_dir, task not deleted: {task.remote_work_dir}",
            )
        server = _get_server_or_400(db, task.server_id)
        executor = SSHExecutor(timeout=CLEANUP_TIMEOUT_SECONDS)
        try:
            executor.connect(
                host=server.host,
                port=server.port,
                username=server.username,
                key_path=server.key_path,
            )
            remote_work_dir_removed = _perform_remote_work_dir_cleanup(executor, task, messages, db)
        except SSHExecutorError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SSH cleanup failed, task not deleted: {exc}",
            ) from exc
        finally:
            executor.close()
    elif not task.remote_work_dir:
        messages.append("remote work dir is empty, skip remote cleanup")
    else:
        messages.append("remote cleanup skipped: apptainer task")

    # 3. Delete task_logs
    logs_count = db.query(TaskLog).filter(TaskLog.task_id == task_id).delete()
    messages.append(f"task logs deleted: {logs_count} entries")

    # 4. Delete task
    db.delete(task)
    db.commit()
    messages.append("task record deleted")

    write_audit_log(
        db, action="task.delete", target_type="task", status="success",
        actor="admin",
        target_id=task_id, target_name=f"{task.file_name or 'unknown'} · {task_id}",
        server_id=task.server_id, task_id=task_id,
        message=f"deleted task {task_id}",
        detail={"task_type": _task_type, "task_status": _task_status, "remote_work_dir_removed": remote_work_dir_removed},
    )

    return TaskDeleteResponse(
        task_id=task.task_id,
        deleted=True,
        local_artifacts_removed=local_artifacts_removed,
        remote_work_dir_removed=remote_work_dir_removed,
        logs_deleted=True,
        task_deleted=True,
        messages=messages,
    )


def _delete_local_artifacts(task_id: str, messages: list[str]) -> bool:
    """Remove local artifact directory for delete. No task_logs writes."""
    if "/" in task_id or ".." in task_id:
        msg = f"local cleanup refused: invalid task_id {task_id}"
        messages.append(msg)
        return False

    artifact_dir = ARTIFACTS_DIR / task_id
    expected_parent = ARTIFACTS_DIR.resolve()

    try:
        resolved = artifact_dir.resolve()
    except (OSError, RuntimeError) as exc:
        msg = f"local cleanup failed: path resolution error: {exc}"
        messages.append(msg)
        return False

    if not str(resolved).startswith(str(expected_parent) + "/"):
        if resolved == expected_parent:
            msg = "local cleanup refused: cannot remove artifacts root directory"
            messages.append(msg)
            return False
        msg = f"local cleanup refused: path escape detected {resolved}"
        messages.append(msg)
        return False

    if not resolved.is_dir():
        msg = "local artifacts not found or already removed"
        messages.append(msg)
        return False

    try:
        shutil.rmtree(resolved)
        msg = f"local artifacts removed: backend/data/artifacts/{task_id}"
        messages.append(msg)
        return True
    except OSError as exc:
        msg = f"local artifacts removal failed: {exc}"
        messages.append(msg)
        return False


def _cleanup_local_artifacts(task_id: str, messages: list[str], db: Session) -> bool:
    """Remove local artifact directory for a completed task with safety checks."""
    if "/" in task_id or ".." in task_id:
        msg = f"local cleanup refused: invalid task_id {task_id}"
        messages.append(msg)
        _add_task_log(db, task_id, "ERROR", msg)
        return False

    artifact_dir = ARTIFACTS_DIR / task_id
    expected_parent = ARTIFACTS_DIR.resolve()

    try:
        resolved = artifact_dir.resolve()
    except (OSError, RuntimeError) as exc:
        msg = f"local cleanup failed: path resolution error: {exc}"
        messages.append(msg)
        _add_task_log(db, task_id, "ERROR", msg)
        return False

    if not str(resolved).startswith(str(expected_parent) + "/"):
        if resolved == expected_parent:
            msg = "local cleanup refused: cannot remove artifacts root directory"
            messages.append(msg)
            _add_task_log(db, task_id, "ERROR", msg)
            return False
        msg = f"local cleanup refused: path escape detected {resolved}"
        messages.append(msg)
        _add_task_log(db, task_id, "ERROR", msg)
        return False

    if not resolved.is_dir():
        msg = "local artifacts not found or already removed"
        messages.append(msg)
        _add_task_log(db, task_id, "SYSTEM", msg)
        return False

    try:
        shutil.rmtree(resolved)
        msg = f"local artifacts removed: backend/data/artifacts/{task_id}"
        messages.append(msg)
        _add_task_log(db, task_id, "SYSTEM", msg)
        return True
    except OSError as exc:
        msg = f"local artifacts removal failed: {exc}"
        messages.append(msg)
        _add_task_log(db, task_id, "ERROR", msg)
        return False


def _perform_remote_work_dir_cleanup(
    executor: SSHExecutor, task: Task, messages: list[str], db: Session,
) -> bool:
    """Remove remote work dir for a completed task. Executor must be connected."""
    remote_work_dir = task.remote_work_dir
    task_id = task.task_id

    if not remote_work_dir:
        return False

    try:
        cmd = f"test -d {shell_quote(remote_work_dir)}"
        ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
        if ec != 0:
            msg = "remote work dir not found or already removed"
            messages.append(msg)
            _add_task_log(db, task_id, "SYSTEM", msg)
            return False

        cmd = f"rm -rf -- {shell_quote(remote_work_dir)}"
        ec, _out, err = executor.exec_capture(cmd, timeout_seconds=CLEANUP_TIMEOUT_SECONDS)
        if ec != 0:
            msg = f"remote work dir removal failed: {err or ec}"
            messages.append(msg)
            _add_task_log(db, task_id, "ERROR", msg)
            return False

        cmd = f"test ! -e {shell_quote(remote_work_dir)}"
        ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
        if ec == 0:
            msg = f"remote work dir removed by cleanup: {remote_work_dir}"
            messages.append(msg)
            _add_task_log(db, task_id, "SYSTEM", msg)
            return True
        else:
            msg = f"remote work dir may not be fully removed: {remote_work_dir}"
            messages.append(msg)
            _add_task_log(db, task_id, "WARN", msg)
            return False
    except (SSHExecutorError, SSHCommandTimeoutError) as exc:
        msg = f"remote work dir cleanup failed: {exc}"
        messages.append(msg)
        _add_task_log(db, task_id, "ERROR", msg)
        return False


@router.post("/{task_id}/monitor", response_model=TaskMonitorResponse)
def task_monitor(
    task_id: str,
    payload: TaskMonitorRequest,
    db: Session = Depends(get_db),
) -> TaskMonitorResponse:
    task = _get_task_or_404(db, task_id)
    server = _get_server_or_400(db, task.server_id)
    command = MONITOR_COMMANDS.get(payload.type)
    if command is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported monitor type")

    executor = SSHExecutor(timeout=MONITOR_TIMEOUT_SECONDS)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )
        exit_code, output, error = executor.exec_capture(command, timeout_seconds=MONITOR_TIMEOUT_SECONDS)
        if exit_code != 0:
            return TaskMonitorResponse(
                success=False,
                type=payload.type,
                output=output or None,
                error=error or f"monitor command exited with code {exit_code}",
                executed_at=datetime.utcnow(),
            )
        return TaskMonitorResponse(
            success=True,
            type=payload.type,
            output=output or "",
            error=None,
            executed_at=datetime.utcnow(),
        )
    except SSHCommandTimeoutError:
        return TaskMonitorResponse(
            success=False,
            type=payload.type,
            output=None,
            error=f"monitor command timed out after {MONITOR_TIMEOUT_SECONDS} seconds",
            executed_at=datetime.utcnow(),
        )
    except SSHExecutorError as exc:
        return TaskMonitorResponse(
            success=False,
            type=payload.type,
            output=None,
            error=str(exc),
            executed_at=datetime.utcnow(),
        )
    finally:
        executor.close()


# ── Structured monitor (Phase 24B) ──

MONITOR_STRUCTURED_TIMEOUT = 8


def _exec_monitor_cmd(executor: SSHExecutor, command: str) -> str | None:
    """Execute a single monitor command, return output or None on failure."""
    try:
        _exit_code, output, _error = executor.exec_capture(command, timeout_seconds=MONITOR_STRUCTURED_TIMEOUT)
        return output or None
    except Exception:
        return None


def _parse_cpu_memory(executor: SSHExecutor) -> dict[str, object]:
    """Parse CPU/memory stats from remote server."""
    result: dict[str, object] = {"available": False, "message": None}
    try:
        # Load average
        load_out = _exec_monitor_cmd(executor, "cat /proc/loadavg 2>/dev/null || echo 'unavailable'")
        if load_out:
            parts = load_out.strip().split()
            if len(parts) >= 3:
                result["load_avg"] = f"{parts[0]} {parts[1]} {parts[2]}"

        # Memory
        mem_out = _exec_monitor_cmd(executor, "free -m 2>/dev/null | grep '^Mem:'")
        if mem_out:
            mem_parts = mem_out.split()
            if len(mem_parts) >= 3:
                total_mb = int(mem_parts[1])
                used_mb = int(mem_parts[2])
                result["memory_total"] = f"{total_mb} MiB"
                result["memory_used"] = f"{used_mb} MiB"
                if total_mb > 0:
                    result["memory_usage_percent"] = round(used_mb / total_mb * 100, 1)

        # CPU usage (short top sample)
        cpu_out = _exec_monitor_cmd(executor, "top -bn1 2>/dev/null | grep 'Cpu(s)' || head -3 /proc/stat")
        if cpu_out:
            m = re.search(r'(\d+\.?\d*)\s*%?\s*id', cpu_out)
            if m:
                idle = float(m.group(1))
                result["cpu_usage_percent"] = round(100.0 - idle, 1)

        # Mark available if at least load or memory or CPU was parsed
        if result.get("load_avg") or result.get("memory_total") is not None or result.get("cpu_usage_percent") is not None:
            result["available"] = True
        else:
            result["message"] = "无法获取 CPU/内存数据"
    except Exception as exc:
        result["message"] = str(exc)
    return result


def _parse_disk(executor: SSHExecutor) -> dict[str, object]:
    """Parse disk usage from df -h output."""
    result: dict[str, object] = {"available": False, "disk_usage": [], "message": None}
    try:
        df_out = _exec_monitor_cmd(executor, "df -h --local 2>/dev/null || df -h 2>/dev/null")
        if not df_out:
            result["message"] = "df 命令不可用"
            return result

        items: list[dict[str, object]] = []
        for line in df_out.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 6 and parts[0].startswith("/"):
                usage_str = parts[4].replace("%", "")
                try:
                    usage_pct = float(usage_str)
                except ValueError:
                    usage_pct = 0.0
                items.append({
                    "mount": parts[5],
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_percent": usage_pct,
                })

        result["disk_usage"] = items
        result["available"] = len(items) > 0
        if not items:
            result["message"] = "未检测到本地磁盘挂载点"
    except Exception as exc:
        result["message"] = str(exc)
    return result


def _parse_gpu(executor: SSHExecutor) -> dict[str, object]:
    """Parse GPU stats from nvidia-smi."""
    result: dict[str, object] = {"available": False, "items": [], "message": None}
    try:
        # Check nvidia-smi availability first
        check = _exec_monitor_cmd(executor, "command -v nvidia-smi 2>/dev/null && echo OK || echo NOT_FOUND")
        if not check or "NOT_FOUND" in check:
            # nvidia-smi unavailable — check lspci for hardware detection
            lspci_check = _exec_monitor_cmd(
                executor,
                "command -v lspci 2>/dev/null && (lspci | grep -qi nvidia && echo HAS_NVIDIA || echo NO_NVIDIA) || echo LSPCI_NA",
            )
            if lspci_check and "HAS_NVIDIA" in lspci_check:
                result["message"] = "检测到 NVIDIA GPU（驱动不可用），无法启动 GPU 监控"
            elif lspci_check and "NO_NVIDIA" in lspci_check:
                result["message"] = "未检测到 NVIDIA GPU"
            else:
                result["message"] = "未检测到 NVIDIA GPU 或 nvidia-smi 不可用"
            return result

        gpu_out = _exec_monitor_cmd(
            executor,
            "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu "
            "--format=csv,noheader,nounits 2>/dev/null",
        )
        if not gpu_out:
            result["message"] = "nvidia-smi 查询无输出"
            return result

        items: list[dict[str, object]] = []
        for line in gpu_out.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            cols = [c.strip() for c in line.split(",")]
            if len(cols) >= 3:
                items.append({
                    "index": cols[0],
                    "name": cols[1] if len(cols) > 1 else "",
                    "utilization_gpu": cols[2] if len(cols) > 2 else None,
                    "memory_used": cols[3] if len(cols) > 3 else None,
                    "memory_total": cols[4] if len(cols) > 4 else None,
                    "temperature": cols[5] if len(cols) > 5 else None,
                })

        result["items"] = items
        result["available"] = len(items) > 0
        if not items:
            result["message"] = "未检测到 GPU 设备"
    except Exception as exc:
        result["message"] = str(exc)
    return result


@router.get("/{task_id}/monitor", response_model=TaskMonitorResponseStructured)
def task_monitor_structured(
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskMonitorResponseStructured:
    task = _get_task_or_404(db, task_id)
    server = _get_server_or_400(db, task.server_id)

    executor = SSHExecutor(timeout=15)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )
        cpu_memory = _parse_cpu_memory(executor)
        disk = _parse_disk(executor)
        gpu = _parse_gpu(executor)

        return TaskMonitorResponseStructured(
            task_id=task.task_id,
            status=task.status,
            sampled_at=datetime.utcnow(),
            cpu_memory=cpu_memory,
            disk=disk,
            gpu=gpu,
        )
    except SSHCommandTimeoutError:
        return TaskMonitorResponseStructured(
            task_id=task.task_id,
            status=task.status,
            sampled_at=datetime.utcnow(),
            cpu_memory={"available": False, "message": "SSH 连接超时"},
            disk={"available": False, "message": "SSH 连接超时"},
            gpu={"available": False, "message": "SSH 连接超时"},
        )
    except SSHExecutorError as exc:
        msg = str(exc)
        return TaskMonitorResponseStructured(
            task_id=task.task_id,
            status=task.status,
            sampled_at=datetime.utcnow(),
            cpu_memory={"available": False, "message": msg},
            disk={"available": False, "message": msg},
            gpu={"available": False, "message": msg},
        )
    finally:
        executor.close()


@router.get("/{task_id}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(task_id: str, db: Session = Depends(get_db)) -> ArtifactListResponse:
    _get_task_or_404(db, task_id)
    artifact_rel_dir = f"backend/data/artifacts/{task_id}/"
    artifacts_dir = ARTIFACTS_DIR / task_id

    files: list[ArtifactFileDetail] = []
    if artifacts_dir.is_dir():
        for entry in artifacts_dir.iterdir():
            if not entry.is_file():
                continue
            files.append(
                ArtifactFileDetail(
                    name=entry.name,
                    size=entry.stat().st_size,
                    type=entry.suffix.lstrip("."),
                    local_relative_path=f"backend/data/artifacts/{task_id}/{entry.name}",
                    download_url=f"/api/tasks/{task_id}/artifacts/{entry.name}/download",
                )
            )

    return ArtifactListResponse(
        artifact_dir=artifact_rel_dir,
        files=files,
    )


@router.get("/{task_id}/artifacts/{filename}/download")
def download_artifact(
    task_id: str,
    filename: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    _get_task_or_404(db, task_id)

    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid filename")

    filepath = (ARTIFACTS_DIR / task_id / safe_name).resolve()
    expected_prefix = (ARTIFACTS_DIR / task_id).resolve()
    if not str(filepath).startswith(str(expected_prefix)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid filename")

    if not filepath.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")

    return FileResponse(
        path=str(filepath),
        media_type="application/octet-stream",
        filename=safe_name,
    )


def _get_library_file_or_400(file_path: str) -> dict[str, object]:
    try:
        return get_library_file_record(file_path)
    except ScriptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _build_remote_work_dir(task_type: str) -> str:
    if task_type == "apptainer":
        return "~/hpcdeploy/apptainer/"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"~/hpcdeploy/tasks/{task_type}/{timestamp}"


def _build_command_preview(
    *,
    task_type: str,
    file_name: str,
    params: dict[str, object] | None,
    remote_work_dir: str,
) -> str:
    script_name = Path(file_name).name
    if task_type == "stress":
        p = params or {}
        dur = p.get("duration_seconds", "?")
        interval = p.get("interval_seconds", 2)

        env_parts: list[str] = []
        if script_name == "cpu_mem_stress_report.sh":
            if "memory_percent" in p:
                env_parts.append(f"MEMORY_PERCENT={p['memory_percent']}")
            if "workers" in p:
                env_parts.append(f"WORKERS={p['workers']}")
        elif script_name == "disk_stress_report.sh":
            if "disk_file_size" in p:
                env_parts.append(f"TEST_FILE_SIZE={p['disk_file_size']}")
            if "disk_path" in p:
                env_parts.append(f"TEST_DIR={p['disk_path']}")
            if "workers" in p:
                env_parts.append(f"WORKERS={p['workers']}")
        elif script_name == "gpu_stress_report.sh":
            gid = p.get("gpu_ids")
            if gid and gid != "all":
                env_parts.append(f"CUDA_VISIBLE_DEVICES={gid}")

        env_prefix = " ".join(env_parts)
        if env_prefix:
            return f"{env_prefix} ./{script_name} {dur} {interval}"
        return f"./{script_name} {dur} {interval}"

    if task_type == "apptainer":
        return f"复制容器到远程目录：{remote_work_dir}"
    return f"bash ./{script_name}"


def _generate_task_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"task-{timestamp}-{token_hex(3)}"


def _add_task_log(db: Session, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()
    # Broadcast via WebSocket (best-effort, must not affect main logic)
    try:
        ws_manager.broadcast_log_sync(task_id, level, message)
    except Exception:
        pass


def _mark_task_canceled(db: Session, task: Task, *, error_message: str, log_message: str) -> None:
    task.status = "CANCELED"
    task.end_time = datetime.utcnow()
    task.exit_code = CANCELED_EXIT_CODE
    task.error_message = error_message
    db.commit()
    _add_task_log(db, task.task_id, "SYSTEM", log_message)
    schedule_report_summary_generation(task.task_id)
    # Broadcast status change
    try:
        ws_manager.broadcast_status_sync(task.task_id, "CANCELED")
        ws_manager.broadcast_done_sync(task.task_id, "CANCELED")
    except Exception:
        pass


def _cancel_following_batch_tasks(db: Session, task: Task, *, reason: str) -> None:
    """Cancel later unfinished tasks in the same batch on the same server.

    This keeps batch state from staying RUNNING when the current task is canceled.
    Only tasks with a higher sequence_index are touched, so previous completed
    steps remain unchanged.
    """
    if not task.batch_id or task.sequence_index is None:
        return

    following_tasks = (
        db.query(Task)
        .filter(
            Task.batch_id == task.batch_id,
            Task.server_id == task.server_id,
            Task.id != task.id,
            Task.sequence_index.isnot(None),
            Task.sequence_index > task.sequence_index,
            Task.status.in_(UNFINISHED_TASK_STATUSES),
        )
        .order_by(Task.sequence_index.asc(), Task.id.asc())
        .all()
    )

    for follower in following_tasks:
        _add_task_log(
            db,
            follower.task_id,
            "SYSTEM",
            f"batch cancel: previous task {task.task_id} canceled, mark this task canceled",
        )
        _mark_task_canceled(db, follower, error_message=reason, log_message="task canceled because previous batch task was canceled")


def _read_remote_pid_file(executor: SSHExecutor, pid_file_path: str) -> str | None:
    command = f"if [ -f {shell_quote(pid_file_path)} ]; then cat {shell_quote(pid_file_path)}; fi"
    exit_code, output, _error = executor.exec_capture(command, timeout_seconds=MONITOR_TIMEOUT_SECONDS)
    if exit_code != 0:
        return None
    value = output.strip()
    if not value:
        return None
    if not value.isdigit():
        raise SSHExecutorError("remote pid file is invalid")
    return value


def _get_remote_process_pgid(executor: SSHExecutor, pid_value: str) -> str | None:
    """Get PGID from a PID. Returns None if process doesn't exist."""
    command = (
        f"if [ ! -d /proc/{shell_quote(pid_value)} ]; then exit 3; fi; "
        f"ps -p {shell_quote(pid_value)} -o pgid= | tr -d ' '"
    )
    exit_code, output, error = executor.exec_capture(command, timeout_seconds=MONITOR_TIMEOUT_SECONDS)
    if exit_code != 0:
        return None
    pgid = output.strip()
    if not pgid or not pgid.isdigit():
        return None
    return pgid


def _kill_remote_process_group(executor: SSHExecutor, pgid: str) -> tuple[bool, str]:
    """Kill process group by PGID. Returns (success, log_message). Never raises."""
    command = (
        f"kill -TERM -{shell_quote(pgid)} 2>/dev/null || true; "
        "sleep 3; "
        f"if ps --no-headers -g {shell_quote(pgid)} >/dev/null 2>&1; then "
        f"  kill -KILL -{shell_quote(pgid)} 2>/dev/null || true; "
        "  sleep 1; "
        f"fi"
    )
    exit_code, _output, error = executor.exec_capture(command, timeout_seconds=10)
    if exit_code != 0:
        return False, error or f"failed to terminate process group {pgid}"
    return True, "remote process group terminated"


def _find_matching_remote_process(executor: SSHExecutor, remote_work_dir: str, script_name: str) -> str | None:
    """Fallback: search /proc for process whose cwd matches remote_work_dir."""
    command = (
        "for proc_dir in /proc/[0-9]*; do "
        "pid=${proc_dir#/proc/}; "
        f"cwd=$(readlink \"$proc_dir/cwd\" 2>/dev/null || true); "
        f"if [ \"$cwd\" != {shell_quote(remote_work_dir)} ]; then continue; fi; "
        "cmd=$(tr '\\0' ' ' < \"$proc_dir/cmdline\" 2>/dev/null || true); "
        f"case \"$cmd\" in *{shell_quote(script_name)}*) printf '%s' \"$pid\"; break ;; esac; "
        "done"
    )
    exit_code, output, _error = executor.exec_capture(command, timeout_seconds=MONITOR_TIMEOUT_SECONDS)
    if exit_code != 0:
        return None
    pid_value = output.strip()
    if not pid_value:
        return None
    if not pid_value.isdigit():
        raise SSHExecutorError("matched remote process pid is invalid")
    return pid_value


def _cancel_remote_process(executor: SSHExecutor, task: Task, db: Session) -> None:
    """Terminate remote process group via PID file + PGID. Best effort — never raises."""
    task_id = task.task_id
    remote_work_dir = task.remote_work_dir

    if not remote_work_dir:
        _add_task_log(db, task_id, "SYSTEM", "no remote work dir, skip process termination")
        return

    # Primary path: read PID file → get PGID → kill process group
    pid_file_path = _build_remote_pid_file_path(remote_work_dir)
    pid_value = _read_remote_pid_file(executor, pid_file_path)

    if pid_value is not None:
        pgid = _get_remote_process_pgid(executor, pid_value)
        if pgid is not None:
            success, log_msg = _kill_remote_process_group(executor, pgid)
            _add_task_log(db, task_id, "SYSTEM", log_msg)
            if not success:
                _add_task_log(db, task_id, "WARN", f"process group {pgid} may have residual processes")
            return
        # PID file exists but process already exited
        _add_task_log(db, task_id, "SYSTEM", "remote process already exited, skipping termination")
        return

    # Fallback: no PID file — search by cwd + script name
    _add_task_log(db, task_id, "SYSTEM", "PID file not found, searching by remote work dir")
    matched_pid = _find_matching_remote_process(executor, remote_work_dir, task.file_name or "")
    if matched_pid is not None:
        pgid = _get_remote_process_pgid(executor, matched_pid)
        if pgid is not None:
            success, log_msg = _kill_remote_process_group(executor, pgid)
            _add_task_log(db, task_id, "SYSTEM", f"fallback: {log_msg}")
            if not success:
                _add_task_log(db, task_id, "WARN", f"fallback: process group {pgid} may have residual processes")
            return

    # No process found at all — still OK, proceed to cleanup
    _add_task_log(db, task_id, "SYSTEM", "no matching remote process found, skipping termination")


def _serialize_task(task: Task, db: Session) -> dict[str, object]:
    return serialize_task_record(task, db)


def _is_safe_remote_work_dir(remote_work_dir: str) -> bool:
    """Strict safety check before rm -rf of a remote work dir.

    Only allows paths matching: <remote_home>/hpcdeploy/tasks/{script,stress,apptainer}/<timestamp>
    Supports both ~ and absolute-path forms.
    """
    if not remote_work_dir:
        return False
    if remote_work_dir == "/":
        return False
    if ".." in remote_work_dir.split("/"):
        return False

    # Explicitly block known unsafe directories
    forbidden_exact = {"/root", "/home", "/tmp", "/opt", "/usr", "/etc"}
    if remote_work_dir.rstrip("/") in forbidden_exact:
        return False

    parts = remote_work_dir.rstrip("/").split("/")
    # Strip leading ~ prefix (home directory placeholder)
    if len(parts) >= 2 and parts[0] == "~":
        parts = parts[1:]
    # Must be at least: hpcdeploy/tasks/<type>/<timestamp> = 4 parts
    if len(parts) < 4:
        return False
    if parts[-4] != "hpcdeploy" or parts[-3] != "tasks":
        return False
    if parts[-2] not in ("script", "stress", "apptainer"):
        return False
    if not parts[-1]:
        return False
    return True


def _cleanup_remote_work_dir(executor: SSHExecutor, task: Task, db: Session) -> None:
    """Remove remote work dir after cancel with strict safety checks."""
    remote_work_dir = task.remote_work_dir
    if not remote_work_dir:
        return
    if task.task_type == "apptainer":
        return

    if not _is_safe_remote_work_dir(remote_work_dir):
        _add_task_log(db, task.task_id, "ERROR", f"remote cleanup refused: unsafe remote_work_dir {remote_work_dir}")
        return

    _add_task_log(db, task.task_id, "SYSTEM", "cleanup remote work dir requested")

    try:
        cmd = f"test -d {shell_quote(remote_work_dir)}"
        ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
        if ec != 0:
            _add_task_log(db, task.task_id, "SYSTEM", "remote work dir already removed or not found")
            return

        cmd = f"rm -rf -- {shell_quote(remote_work_dir)}"
        ec, _out, err = executor.exec_capture(cmd, timeout_seconds=30)
        if ec != 0:
            _add_task_log(db, task.task_id, "ERROR", f"remote work dir cleanup failed: {err or ec}")
            return

        cmd = f"test ! -e {shell_quote(remote_work_dir)}"
        ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
        if ec == 0:
            _add_task_log(db, task.task_id, "SYSTEM", f"remote work dir removed: {remote_work_dir}")
        else:
            _add_task_log(db, task.task_id, "WARN", f"remote work dir may not be fully removed: {remote_work_dir}")
    except (SSHExecutorError, SSHCommandTimeoutError) as exc:
        _add_task_log(db, task.task_id, "ERROR", f"remote work dir cleanup failed: {exc}")


def _get_temp_dirs_for_script(script_name: str) -> list[str]:
    """Return temp download dirs allowed for this script, or empty list."""
    return SCRIPT_TEMP_DIR_MAP.get(script_name, [])


def _is_safe_temp_dir(tmp_dir: str) -> bool:
    """Strict safety check before rm -rf of a temp download dir.

    Only exact matches from the backend whitelist are allowed.
    No frontend input, no wildcards, no path traversal.
    """
    if not tmp_dir:
        return False
    if tmp_dir == "/tmp":
        return False
    if ".." in tmp_dir.split("/"):
        return False
    # Must be an exact match from the backend-only whitelist
    if tmp_dir not in ALLOWED_TEMP_DIRS:
        return False
    return True


def _cleanup_temp_dirs(executor: SSHExecutor, task: Task, db: Session) -> None:
    """Clean up temp download dirs for known whitelist scripts. Best effort — never raises."""
    script_name = task.file_name or ""
    temp_dirs = _get_temp_dirs_for_script(script_name)
    if not temp_dirs:
        return

    _add_task_log(db, task.task_id, "SYSTEM", "cleanup temp download dir requested")
    for tmp_dir in temp_dirs:
        if not _is_safe_temp_dir(tmp_dir):
            _add_task_log(db, task.task_id, "ERROR", f"temp download dir cleanup refused: unsafe path {tmp_dir}")
            continue

        try:
            # Check if directory exists
            cmd = f"test -d {shell_quote(tmp_dir)}"
            ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
            if ec != 0:
                _add_task_log(db, task.task_id, "SYSTEM", f"temp download dir not found or already removed: {tmp_dir}")
                continue

            # Remove directory
            cmd = f"rm -rf -- {shell_quote(tmp_dir)}"
            ec, _out, err = executor.exec_capture(cmd, timeout_seconds=CLEANUP_TIMEOUT_SECONDS)
            if ec != 0:
                _add_task_log(db, task.task_id, "ERROR", f"temp download dir cleanup failed: {err or ec}")
                continue

            # Verify removal
            cmd = f"test ! -e {shell_quote(tmp_dir)}"
            ec, _out, _err = executor.exec_capture(cmd, timeout_seconds=10)
            if ec == 0:
                _add_task_log(db, task.task_id, "SYSTEM", f"temp download dir removed: {tmp_dir}")
            else:
                _add_task_log(db, task.task_id, "WARN", f"temp download dir may not be fully removed: {tmp_dir}")
        except (SSHExecutorError, SSHCommandTimeoutError) as exc:
            _add_task_log(db, task.task_id, "ERROR", f"temp download dir cleanup failed: {exc}")
