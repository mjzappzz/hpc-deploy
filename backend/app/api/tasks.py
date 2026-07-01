import shutil
import re
import threading
from datetime import datetime
from pathlib import Path
from secrets import token_hex

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
    run_task_stage8b,
)
from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.task_diagnosis import diagnose_task_failure
from app.core.ws_manager import ws_manager
from app.db.database import SessionLocal, get_db
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.log import TaskLogRead
from app.schemas.task import (
    ArtifactFileDetail,
    ArtifactListResponse,
    BatchDetailResponse,
    BatchSummaryItem,
    BatchSummaryListResponse,
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
from fastapi.responses import FileResponse, Response
from sqlalchemy import case, func
from sqlalchemy.orm import Session

# Stress param whitelists
STRESS_ALLOWED_INTERVALS: list[int] = [5, 10, 30, 60, 120]
STRESS_ALLOWED_DISK_FILE_SIZES: list[str] = ["1G", "10G", "50G", "100G"]
STRESS_ALLOWED_GPU_BACKENDS: list[str] = ["cuda"]
STRESS_ALL_PARAM_KEYS: set[str] = {
    "duration_seconds", "interval_seconds",
    "memory_percent", "workers",
    "disk_file_size", "disk_path", "disk_test_dir",
    "gpu_ids", "gpu_memory_percent", "gpu_backend",
}

_SAFE_DISK_DIR_PREFIXES: tuple[str, ...] = (
    "/data", "/mnt", "/scratch", "/public", "/home", "/root",
)

_SAFE_DISK_DIR_BLOCKLIST: tuple[str, ...] = (
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    "/boot", "/dev", "/proc", "/sys", "/run", "/var", "/tmp",
)

_DISK_DIR_DANGEROUS_CHARS: re.Pattern = re.compile(r"[;&|`$()\n\r\0 \*\?]")
_DISK_DIR_TRAVERSAL: str = ".."

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

def _auto_calc_stress_interval(duration_seconds: int) -> int:
    """Auto-calculate sampling interval based on duration."""
    if duration_seconds <= 600:
        return 10
    if duration_seconds <= 3600:
        return 30
    if duration_seconds <= 43200:
        return 60
    return 120


def _validate_disk_test_dir(path: str) -> str:
    """Validate disk_test_dir for disk stress tasks.

    Rules:
      1. Must be absolute (starts with /).
      2. Must start with one of the safe prefixes.
      3. No path traversal (..).
      4. No dangerous shell chars or spaces.
      5. Not a blocked system directory.
      6. No trailing wildcards.

    Returns the cleaned (trimmed) path, or raises HTTPException(400).
    """
    stripped = path.strip()

    if not stripped.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must be an absolute path",
        )

    if _DISK_DIR_TRAVERSAL in stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must not contain path traversal (..)",
        )

    if _DISK_DIR_DANGEROUS_CHARS.search(stripped):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir contains dangerous characters",
        )

    if stripped.endswith(("*", "?")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must not end with wildcard character",
        )

    if stripped in _SAFE_DISK_DIR_BLOCKLIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"disk_test_dir must not be a system directory ({stripped})",
        )

    if not stripped.startswith(_SAFE_DISK_DIR_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"disk_test_dir must start with one of: {', '.join(_SAFE_DISK_DIR_PREFIXES)}",
        )

    return stripped


def _validate_stress_params(raw: dict[str, object], script_name: str) -> dict[str, object]:
    """Validate and sanitize stress task params.
    Raises HTTPException(400) on any invalid value.
    Returns a cleaned params dict with only accepted keys.
    """
    validated: dict[str, object] = {}

    # duration_seconds: required, 10 ~ 259200
    dur = raw.get("duration_seconds")
    if not isinstance(dur, int) or dur < 10 or dur > 259200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_seconds must be an integer between 10 and 259200",
        )
    validated["duration_seconds"] = dur

    # interval_seconds: auto-calculated, always overridden
    validated["interval_seconds"] = _auto_calc_stress_interval(dur)

    # --- cpu_mem_stress_report.sh params ---
    if script_name == "cpu_mem_stress_report.sh":
        if "memory_percent" in raw:
            mp = raw["memory_percent"]
            if not isinstance(mp, int) or mp < 10 or mp > 95:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="memory_percent must be between 10 and 95")
            validated["memory_percent"] = mp
        if "workers" in raw:
            w = raw["workers"]
            if not isinstance(w, int) or w < 1 or w > 1024:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workers must be between 1 and 1024")
            validated["workers"] = w

    # --- disk_stress_report.sh params ---
    elif script_name == "disk_stress_report.sh":
        if "disk_file_size" in raw:
            dfs = raw["disk_file_size"]
            if dfs not in STRESS_ALLOWED_DISK_FILE_SIZES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"disk_file_size must be one of {STRESS_ALLOWED_DISK_FILE_SIZES}",
                )
            validated["disk_file_size"] = dfs
        if "disk_path" in raw:
            dp = raw["disk_path"]
            if not isinstance(dp, str) or not dp.startswith("~/") or ".." in dp:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disk_path must be under home directory (~/...)")
            validated["disk_path"] = dp
        if "disk_test_dir" in raw:
            dtd = raw["disk_test_dir"]
            if not isinstance(dtd, str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disk_test_dir must be a string")
            if dtd.strip():
                validated["disk_test_dir"] = _validate_disk_test_dir(dtd)
            # else empty string → pass empty; backend will use remote_work_dir

    # --- gpu_stress_report.sh params ---
    elif script_name == "gpu_stress_report.sh":
        if "gpu_ids" in raw:
            gpu_ids = raw["gpu_ids"]
            if not isinstance(gpu_ids, str) or not re.match(r'^(\d+(,\d+)*|all)$', gpu_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="gpu_ids must be 'all' or comma-separated numbers (e.g. '0,1')",
                )
            validated["gpu_ids"] = gpu_ids
        if "gpu_memory_percent" in raw:
            gmp = raw["gpu_memory_percent"]
            if not isinstance(gmp, int) or gmp < 10 or gmp > 95:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gpu_memory_percent must be between 10 and 95")
            validated["gpu_memory_percent"] = gmp
        if "gpu_backend" in raw:
            if raw["gpu_backend"] not in STRESS_ALLOWED_GPU_BACKENDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"gpu_backend must be one of {STRESS_ALLOWED_GPU_BACKENDS}",
                )
            validated["gpu_backend"] = "cuda"

    # Reject unknown keys
    for key in raw:
        if key not in STRESS_ALL_PARAM_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown param: {key}")

    return validated


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
VALID_TASK_TYPES: frozenset[str] = frozenset({"script", "stress", "apptainer"})
VALID_ORDER_VALUES: frozenset[str] = frozenset({"created_desc", "created_asc"})


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
    server_id: int | None = Query(None, ge=1),
    keyword: str | None = Query(None, min_length=1),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("created_desc"),
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
    if order not in VALID_ORDER_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid order: {order}",
        )

    # --- build query ---
    query = db.query(Task)

    if task_status is not None:
        query = query.filter(Task.status == task_status)
    if task_type is not None:
        query = query.filter(Task.task_type == task_type)
    if server_id is not None:
        query = query.filter(Task.server_id == server_id)
    if keyword is not None:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            Task.task_id.ilike(like_pattern)
            | Task.file_path.ilike(like_pattern)
            | Task.remote_work_dir.ilike(like_pattern)
            | Task.error_message.ilike(like_pattern)
        )

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

        validated = _validate_stress_params(raw_params, str(file_record["name"]))
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
        params = _validate_stress_params(payload.params, script_name)
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


def _run_stress_suite_for_server(server_id: int, batch_id: str) -> None:
    """Run stress suite tasks sequentially for a single server.

    Tasks are ordered by sequence_index (GPU → CPU/mem → Disk).
    Each task runs in series; failure of one does not stop subsequent tasks.
    Different server threads run in parallel (daemon threads).
    """
    db = SessionLocal()
    try:
        task_records = (
            db.query(Task)
            .filter(Task.batch_id == batch_id, Task.server_id == server_id)
            .order_by(Task.sequence_index)
            .all()
        )
    finally:
        db.close()

    for task in task_records:
        try:
            run_task_stage8b(task.task_id)
        except Exception:
            pass  # run_task_stage8b handles its own error logging


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
        if key not in STRESS_ALL_PARAM_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown param: {key}",
            )

    # duration_seconds: required
    dur = raw.get("duration_seconds")
    if not isinstance(dur, int) or dur < 10 or dur > 259200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_seconds must be an integer between 10 and 259200",
        )

    # Build shared params
    suite_params: dict[str, object] = {
        "duration_seconds": dur,
        "interval_seconds": _auto_calc_stress_interval(dur),
    }

    # Copy through other whitelisted params
    for key in raw:
        if key not in ("duration_seconds", "interval_seconds"):
            suite_params[key] = raw[key]

    # Validate disk_test_dir if disk is selected
    has_disk = any(s["name"] == "disk_stress_report.sh" for s in selected_scripts)
    dtd = suite_params.get("disk_test_dir")
    if dtd is not None and has_disk:
        if isinstance(dtd, str) and dtd.strip():
            suite_params["disk_test_dir"] = _validate_disk_test_dir(dtd)

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


# ── Batch summary / detail (Phase 26A) ──

VALID_BATCH_STATUS_VALUES = {"RUNNING", "SUCCESS", "FAILED", "PARTIAL_FAILED", "CANCELED", "PARTIAL_CANCELED"}


def _compute_batch_status(tasks: list[Task]) -> str:
    """Derive the aggregate batch status from its child tasks."""
    statuses = {t.status for t in tasks}
    unfinished = {"PENDING", "RUNNING", "CONNECTING", "PREPARING", "UPLOADING", "CANCELING"}

    if statuses & unfinished:
        return "RUNNING"
    if statuses == {"SUCCESS"}:
        return "SUCCESS"
    if statuses == {"FAILED"}:
        return "FAILED"
    if statuses == {"CANCELED"}:
        return "CANCELED"
    if "CANCELED" in statuses and "SUCCESS" not in statuses and "FAILED" not in statuses:
        return "CANCELED"
    if "CANCELED" in statuses:
        return "PARTIAL_CANCELED"
    if "FAILED" in statuses:
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
    subq = (
        db.query(
            Task.batch_id,
            func.min(Task.task_type).label("task_type"),
            func.min(Task.created_at).label("created_at"),
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == "SUCCESS", 1), else_=0)).label("success"),
            func.sum(case((Task.status == "FAILED", 1), else_=0)).label("failed"),
            func.sum(case((Task.status.in_({"RUNNING", "PENDING", "CONNECTING", "PREPARING", "UPLOADING", "CANCELING"}), 1), else_=0)).label("running"),
            func.sum(case((Task.status == "PENDING", 1), else_=0)).label("pending"),
            func.sum(case((Task.status == "CANCELED", 1), else_=0)).label("canceled"),
        )
        .filter(Task.batch_id.isnot(None))
        .group_by(Task.batch_id)
        .subquery()
    )

    # Build main query from subquery
    q = db.query(subq)

    if status is not None:
        # We need to filter by computed status — re-derive in SQL is complex;
        # instead filter after fetching. Limit pre-fetch.
        pass

    if keyword is not None:
        q = q.filter(subq.c.batch_id.ilike(f"%{keyword}%"))

    total_q = q.count()
    items_q = q.order_by(subq.c.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items: list[BatchSummaryItem] = []
    for row in items_q:
        # Fetch server names and distinct script names for this batch
        child_tasks = (
            db.query(Task).filter(Task.batch_id == row.batch_id).all()
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

        raw_status = _compute_batch_status(child_tasks)

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
        ))

    return BatchSummaryListResponse(
        items=items,
        total=len(items) + total_q - len(items_q),  # approx if filtered
        page=page,
        page_size=page_size,
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
        .filter(Task.batch_id == batch_id)
        .order_by(Server.name.asc().nulls_last(), Task.sequence_index.asc().nulls_last(), Task.id.asc())
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")

    # Build summary
    server_names: list[str] = []
    detail_items: list[BatchTaskDetailItem] = []
    total = len(tasks)
    success = failed = running = pending = canceled = 0
    for t in tasks:
        srv = db.get(Server, t.server_id)
        srv_name = srv.name if srv else "unknown"
        srv_host = srv.host if srv else ""

        if srv and srv.name not in server_names:
            server_names.append(srv.name)

        # Count statuses
        if t.status == "SUCCESS":
            success += 1
        elif t.status == "FAILED":
            failed += 1
        elif t.status in {"RUNNING", "PENDING", "CONNECTING", "PREPARING", "UPLOADING", "CANCELING"}:
            running += 1
        elif t.status == "CANCELED":
            canceled += 1
        elif t.status == "PENDING":
            pending += 1

        has_artifacts = bool(t.status == "SUCCESS" and t.task_id)
        # Quick check if artifact dir exists
        if has_artifacts:
            artifact_dir = ARTIFACTS_DIR / t.task_id
            has_artifacts = artifact_dir.is_dir()

        # 计算耗时（秒）
        _dur: int | None = None
        if t.start_time and t.end_time:
            _delta = t.end_time - t.start_time
            _dur = int(_delta.total_seconds())

        task_name = f"{srv_name} · {t.task_type or 'task'} · {t.file_name or 'unknown'}"

        detail_items.append(BatchTaskDetailItem(
            task_id=t.task_id,
            task_name=task_name,
            server_id=t.server_id,
            server_name=srv_name,
            host=srv_host,
            status=t.status,
            sequence_index=t.sequence_index,
            started_at=t.start_time,
            ended_at=t.end_time,
            duration_seconds=_dur,
            exit_code=t.exit_code,
            has_artifacts=has_artifacts,
            error_summary=t.error_message,
        ))

    batch_status = _compute_batch_status(tasks)

    # Collect distinct script names
    script_names: set[str] = set()
    for t in tasks:
        if t.file_name:
            script_names.add(t.file_name)

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
    )

    return BatchDetailResponse(
        batch_id=batch_id,
        summary=summary,
        tasks=detail_items,
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
        finally:
            db.close()

        # Send current status
        await ws_manager.broadcast_status(task_id, task.status)

        # Keep connection alive, handle incoming (mostly pings from client)
        while True:
            try:
                data = await ws.receive_text()
                # Client sent a message — ignore (could be ping/pong)
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        ws_manager.disconnect(task_id, ws)


@router.get("/{task_id}/diagnosis", response_model=TaskDiagnosisResponse)
def diagnose_task(task_id: str, db: Session = Depends(get_db)) -> TaskDiagnosisResponse:
    """Diagnose a task failure based on its logs."""
    task = _get_task_or_404(db, task_id)

    # Build task display name
    host = db.query(Server).with_entities(Server.host).filter(Server.id == task.server_id).scalar() or "?"
    task_name = f"{host} · {task.file_name or task.task_type} · {task.task_id}"

    # Fetch logs
    log_rows = (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.id.asc())
        .all()
    )
    log_messages: list[str] = [row.message for row in log_rows] if log_rows else []
    if not log_messages and task.error_message:
        log_messages = [task.error_message]

    # Run diagnosis
    diagnosis = diagnose_task_failure(
        task_status=task.status,
        error_message=task.error_message,
        logs=log_messages,
    )

    # Audit log (best-effort, must not affect response)
    try:
        write_audit_log(
            db, action="task.diagnose", target_type="task", status="success",
            target_id=task_id, target_name=task_name,
            task_id=task_id, server_id=task.server_id,
            message=f"diagnose task {task_id}: {diagnosis.get('category', 'unknown')}",
            detail={"category": diagnosis.get("category"), "level": diagnosis.get("level"),
                    "file_name": task.file_name, "task_status": task.status},
        )
    except Exception:
        pass

    return TaskDiagnosisResponse(
        task_id=task.task_id,
        task_name=task_name,
        status=task.status,
        diagnosis=diagnosis,
    )


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
def cancel_task(
    task_id: str,
    payload: TaskCancelRequest = TaskCancelRequest(),
    db: Session = Depends(get_db),
) -> TaskCancelResponse:
    task = _get_task_or_404(db, task_id)
    original_status = task.status
    if task.status in TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task already completed")
    if task.status == "CANCELING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="task is already canceling")
    if task.status not in CANCELABLE_TASK_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is not cancelable")

    task.status = "CANCELING"
    db.commit()
    _add_task_log(db, task_id, "SYSTEM", "cancel requested by user")

    if not task.remote_work_dir:
        _mark_task_canceled(
            db,
            task,
            error_message="canceled by user before remote execution",
            log_message="task canceled before remote execution",
        )
        write_audit_log(
            db, action="task.cancel", target_type="task", status="success",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"task {task_id} canceled before remote execution",
        )
        return TaskCancelResponse(task_id=task.task_id, status=task.status)

    server = _get_server_or_400(db, task.server_id)
    executor = SSHExecutor(timeout=MONITOR_TIMEOUT_SECONDS)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )

        # Phase 1: Terminate remote process (best effort — never revert CANCELED)
        _cancel_remote_process(executor, task, db)

        # Phase 2: Mark canceled
        db.refresh(task)
        if task.status == "CANCELING":
            _mark_task_canceled(
                db,
                task,
                error_message="canceled by user",
                log_message="task canceled",
            )

        # Phase 3: 先尝试回收 artifact（无论是否删除，先拉回报告）
        _add_task_log(db, task_id, "SYSTEM", f"cancel: delete_remote_files={payload.delete_remote_files} (type={type(payload.delete_remote_files).__name__})")
        try:
            from app.core.artifact_collector import collect_artifacts
            collect_artifacts(db, task_id, task.remote_work_dir, executor)
        except Exception:
            _add_task_log(db, task_id, "SYSTEM", "cancel: artifact collection skipped (best effort)")

        # Phase 3b: 只有用户明确勾选时才删除远端工作目录
        if payload.delete_remote_files is True:
            _add_task_log(db, task_id, "SYSTEM", "cancel: user requested remote work dir deletion")
            _cleanup_remote_work_dir(executor, task, db)
        else:
            _add_task_log(db, task_id, "SYSTEM", "cancel: preserving remote work dir (user opted to keep files)")

        # Phase 4: Cleanup temp download dirs for known whitelist scripts (best effort)
        _cleanup_temp_dirs(executor, task, db)

        write_audit_log(
            db, action="task.cancel", target_type="task", status="success",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"task {task_id} canceled",
            detail={"server_id": task.server_id, "delete_remote_files": payload.delete_remote_files},
        )
        return TaskCancelResponse(task_id=task.task_id, status=task.status)
    except SSHExecutorError as exc:
        db.refresh(task)
        if task.status == "CANCELING":
            task.status = original_status
            db.commit()
        _add_task_log(db, task_id, "ERROR", f"cancel failed: {exc}")
        write_audit_log(
            db, action="task.cancel", target_type="task", status="failed",
            actor="visitor",
            target_id=task_id, target_name=task.file_name or "unknown",
            task_id=task_id, server_id=task.server_id,
            message=f"cancel failed for {task_id}: {exc}",
            detail={"error": str(exc), "server_id": task.server_id},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"cancel failed: {exc}") from exc
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
    # Broadcast status change
    try:
        ws_manager.broadcast_status_sync(task.task_id, "CANCELED")
        ws_manager.broadcast_done_sync(task.task_id, "CANCELED")
    except Exception:
        pass


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


def _parse_task_duration_seconds(task: Task) -> int | None:
    """Extract duration_seconds from task params or command_preview."""
    if task.params and isinstance(task.params, dict):
        ds = task.params.get("duration_seconds")
        if isinstance(ds, int) and ds > 0:
            return ds
    # Try to parse from command_preview for stress tasks
    if task.task_type == "stress" and task.command_preview:
        m = re.search(r'(\d+)', task.command_preview)
        if m:
            val = int(m.group(1))
            return val if val > 0 else None
    return None


def _serialize_task(task: Task, db: Session) -> dict[str, object]:
    server = db.get(Server, task.server_id)
    return {
        "id": task.id,
        "task_id": task.task_id,
        "server_id": task.server_id,
        "server_name": server.name if server else None,
        "server_host": server.host if server else None,
        "script_id": task.script_id,
        "task_type": task.task_type,
        "file_path": task.file_path,
        "file_name": task.file_name,
        "display_category": task.display_category,
        "remote_work_dir": task.remote_work_dir,
        "command_preview": task.command_preview,
        "status": task.status,
        "batch_id": task.batch_id,
        "params": task.params,
        "start_time": task.start_time,
        "end_time": task.end_time,
        "exit_code": task.exit_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "duration_seconds": _parse_task_duration_seconds(task),
    }


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
