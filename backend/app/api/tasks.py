from datetime import datetime
from pathlib import Path
from secrets import token_hex

from app.core.script_library import get_library_file_record
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError
from app.core.script_validator import ScriptValidationError
from app.core.task_runner import run_task_stage8b
from app.core.artifact_collector import ARTIFACTS_DIR
from app.db.database import get_db
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.log import TaskLogRead
from app.schemas.task import ArtifactFileDetail, ArtifactListResponse, TaskMonitorRequest, TaskMonitorResponse, TaskRead, TaskRunRequest, TaskRunResponse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tasks", tags=["tasks"])

MAX_STRESS_DURATION_SECONDS = 3600
MONITOR_TIMEOUT_SECONDS = 10
RUNNING_STATUSES = ("PENDING", "CONNECTING", "PREPARING", "UPLOADING", "RUNNING")

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
        .filter(Task.server_id == payload.server_id, Task.status.in_(RUNNING_STATUSES))
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
    if task_type == "apptainer":
        return f"复制容器到远程目录：{remote_work_dir}"
    return f"bash ./{script_name}"


def _generate_task_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"task-{timestamp}-{token_hex(3)}"


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
