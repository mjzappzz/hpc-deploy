import shutil
from datetime import datetime
from pathlib import Path
from secrets import token_hex

from app.core.script_library import get_library_file_record
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError, shell_quote
from app.core.script_validator import ScriptValidationError
from app.core.task_runner import (
    ALLOWED_MPI_FILENAMES,
    CANCELABLE_TASK_STATUSES,
    CANCELED_EXIT_CODE,
    PID_FILE_NAME,
    TERMINAL_TASK_STATUSES,
    TEST_ALLOWED_FILENAMES,
    UNFINISHED_TASK_STATUSES,
    _build_remote_pid_file_path,
    run_task_stage8b,
)
from app.core.artifact_collector import ARTIFACTS_DIR
from app.db.database import get_db
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.log import TaskLogRead
from app.schemas.task import ArtifactFileDetail, ArtifactListResponse, TaskCancelResponse, TaskCleanupResponse, TaskDeleteResponse, TaskMonitorRequest, TaskMonitorResponse, TaskRead, TaskRunRequest, TaskRunResponse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tasks", tags=["tasks"])

MAX_STRESS_DURATION_SECONDS = 3600
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

MPI_TASK_BLOCKED_MESSAGE = (
    "当前阶段只允许执行 mpi_env_test.sh、install_oneapi_2022.sh、"
    "install_openmpi_4.1.6_aocc_aocl.sh。"
)
TEST_TASK_BLOCKED_MESSAGE = "当前阶段只允许执行 hello.sh、sleep_60.sh。"

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


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    tasks = db.query(Task).order_by(Task.id.desc()).all()
    return [_serialize_task(task, db) for task in tasks]


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

    if file_record["physical_category"] != payload.task_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_type does not match knowledge base file category",
        )
    if payload.task_type == "mpi" and str(file_record["name"]) not in ALLOWED_MPI_FILENAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MPI_TASK_BLOCKED_MESSAGE)
    if payload.task_type == "test" and str(file_record["name"]) not in TEST_ALLOWED_FILENAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=TEST_TASK_BLOCKED_MESSAGE)

    params: dict[str, object] | None = None
    if payload.task_type == "stress":
        if payload.duration_seconds is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="duration_seconds is required")
        if payload.duration_seconds > MAX_STRESS_DURATION_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duration_seconds must be less than or equal to 3600",
            )
        params = {"duration_seconds": payload.duration_seconds}
    elif payload.duration_seconds is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_seconds is only allowed for stress tasks",
        )

    remote_work_dir = _build_remote_work_dir(payload.task_type)
    command_preview = _build_command_preview(
        task_type=payload.task_type,
        file_name=str(file_record["name"]),
        duration_seconds=payload.duration_seconds,
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
    background_tasks.add_task(run_task_stage8b, task_id)
    return TaskRunResponse(task_id=task_id, status="PENDING")


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


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
def cancel_task(task_id: str, db: Session = Depends(get_db)) -> TaskCancelResponse:
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

        # Phase 3: Cleanup remote work dir (best effort)
        _cleanup_remote_work_dir(executor, task, db)

        # Phase 4: Cleanup temp download dirs for known whitelist scripts (best effort)
        _cleanup_temp_dirs(executor, task, db)

        return TaskCancelResponse(task_id=task.task_id, status=task.status)
    except SSHExecutorError as exc:
        db.refresh(task)
        if task.status == "CANCELING":
            task.status = original_status
            db.commit()
        _add_task_log(db, task_id, "ERROR", f"cancel failed: {exc}")
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
def delete_task(task_id: str, db: Session = Depends(get_db)) -> TaskDeleteResponse:
    task = _get_task_or_404(db, task_id)

    if task.status not in TERMINAL_TASK_STATUSES:
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
    duration_seconds: int | None,
    remote_work_dir: str,
) -> str:
    script_name = Path(file_name).name
    if task_type == "stress":
        return f"./{script_name} {duration_seconds}"
    if task_type == "mpi":
        return f"bash ./{script_name}"
    if task_type == "apptainer":
        return f"复制容器到远程目录：{remote_work_dir}"
    return f"bash ./{script_name}"


def _generate_task_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"task-{timestamp}-{token_hex(3)}"


def _add_task_log(db: Session, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()


def _mark_task_canceled(db: Session, task: Task, *, error_message: str, log_message: str) -> None:
    task.status = "CANCELED"
    task.end_time = datetime.utcnow()
    task.exit_code = CANCELED_EXIT_CODE
    task.error_message = error_message
    db.commit()
    _add_task_log(db, task.task_id, "SYSTEM", log_message)


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
        "params": task.params,
        "start_time": task.start_time,
        "end_time": task.end_time,
        "exit_code": task.exit_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _is_safe_remote_work_dir(remote_work_dir: str) -> bool:
    """Strict safety check before rm -rf of a remote work dir.

    Only allows paths matching: <remote_home>/hpcdeploy/tasks/{test,stress,mpi}/<timestamp>
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
    if parts[-2] not in ("test", "stress", "mpi"):
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
