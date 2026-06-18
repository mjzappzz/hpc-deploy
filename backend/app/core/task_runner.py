from datetime import datetime
from pathlib import Path

from app.core.script_library import get_library_file_record, resolve_library_path
from app.core.script_validator import ScriptValidationError
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError
from app.db.database import SessionLocal
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog

APPTAINER_REMOTE_DIR_SUFFIX = "/hpcdeploy/apptainer"


def run_task_stage8b(task_id: str) -> None:
    db = SessionLocal()
    executor = SSHExecutor()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None:
            return
        _set_status(db, task, "CONNECTING")
        _add_log(
            db,
            task_id,
            "SYSTEM",
            "connecting" if task.task_type == "apptainer" else f"connecting to server {task.server_id}",
        )

        server = db.get(Server, task.server_id)
        if server is None:
            raise TaskRunnerError("server not found")

        file_record = _resolve_task_library_file(task.file_path, task.task_type)
        _validate_task_file_type(task, file_record)
        local_path = resolve_library_path(str(task.file_path))

        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )
        _add_log(db, task_id, "SYSTEM", "connected")

        remote_home = executor.get_remote_home()
        _add_log(db, task_id, "SYSTEM", f"remote HOME detected: {remote_home}")

        remote_dir = _resolve_remote_work_dir(task.task_type, remote_home)
        task.remote_work_dir = remote_dir
        db.commit()
        _add_log(db, task_id, "SYSTEM", f"remote work dir resolved: {remote_dir}")

        remote_path = _build_remote_path(remote_dir, str(file_record["name"]))

        _set_status(db, task, "PREPARING")
        _mark_task_started(db, task)
        _add_log(
            db,
            task_id,
            "SYSTEM",
            "creating remote directory" if task.task_type == "apptainer" else f"creating remote directory {remote_dir}",
        )
        executor.mkdir_p(remote_dir)

        _set_status(db, task, "UPLOADING")
        _add_log(
            db,
            task_id,
            "SYSTEM",
            "uploading apptainer file" if task.task_type == "apptainer" else f"uploading {task.file_path}",
        )
        executor.upload_file(str(local_path), remote_path)
        _add_log(db, task_id, "SYSTEM", f"uploaded to {remote_path}")

        if _should_chmod(local_path):
            _add_log(db, task_id, "SYSTEM", "running chmod +x")
            executor.chmod(remote_path, 0o755)
            _add_log(db, task_id, "SYSTEM", "chmod +x completed")

        if task.task_type == "test":
            _execute_command_task(db, executor, task, task_id, _build_test_command(task.file_name))
        elif task.task_type == "stress":
            _execute_command_task(db, executor, task, task_id, _build_stress_command(task))
            if task.remote_work_dir:
                try:
                    from app.core.artifact_collector import collect_artifacts

                    collect_artifacts(db, task_id, task.remote_work_dir, executor)
                except Exception:
                    _add_log(db, task_id, "ERROR", "artifact collection failed")
        elif task.task_type == "apptainer":
            _add_log(db, task_id, "SYSTEM", "apptainer distribution completed, file was uploaded but not executed")
            task.status = "SUCCESS"
            task.exit_code = 0
            task.end_time = datetime.utcnow()
            task.error_message = None
            db.commit()
        else:
            _add_log(db, task_id, "SYSTEM", "stage 8B completed, script was uploaded but not executed")
            task.status = "SUCCESS"
            task.exit_code = 0
            task.end_time = datetime.utcnow()
            task.error_message = None
            db.commit()
    except (TaskRunnerError, SSHExecutorError, ScriptValidationError) as exc:
        _fail_task(db, task_id, str(exc))
    except Exception:
        _fail_task(db, task_id, "task preparation failed")
    finally:
        executor.close()
        db.close()


class TaskRunnerError(Exception):
    pass


def _resolve_task_library_file(file_path: str | None, task_type: str | None) -> dict[str, object]:
    if not file_path:
        raise TaskRunnerError("task file_path is empty")
    if not task_type:
        raise TaskRunnerError("task type is empty")

    record = get_library_file_record(file_path)
    if record["physical_category"] != task_type:
        raise TaskRunnerError("task_type does not match knowledge base file category")
    return record


def _validate_task_file_type(task: Task, file_record: dict[str, object]) -> None:
    file_name = str(file_record["name"])
    suffix = Path(file_name).suffix.lower()
    if task.task_type == "apptainer" and suffix != ".sif":
        raise TaskRunnerError("apptainer task only allows .sif files")
    if task.task_type == "apptainer" and suffix in {".sh", ".py"}:
        raise TaskRunnerError("apptainer task does not allow shell or python scripts")


def _build_remote_path(remote_dir: str, file_name: str) -> str:
    remote_dir_clean = remote_dir.rstrip("/")
    return f"{remote_dir_clean}/{Path(file_name).name}"


def _resolve_remote_work_dir(task_type: str | None, remote_home: str) -> str:
    if not task_type:
        raise TaskRunnerError("task type is empty")
    base_home = remote_home.rstrip("/")
    if task_type == "apptainer":
        return f"{base_home}{APPTAINER_REMOTE_DIR_SUFFIX}"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{base_home}/hpcdeploy/tasks/{task_type}/{timestamp}"


def _execute_command_task(db, executor: SSHExecutor, task: Task, task_id: str, command: str) -> None:
    if not task.file_name:
        raise TaskRunnerError("task file_name is empty")
    if not task.remote_work_dir:
        raise TaskRunnerError("task remote_work_dir is empty")

    timeout_seconds = _resolve_command_timeout(task)
    task.start_time = datetime.utcnow()
    db.commit()
    _set_status(db, task, "RUNNING")
    _add_log(db, task_id, "SYSTEM", f"command timeout set to {timeout_seconds} seconds")
    _add_log(db, task_id, "SYSTEM", f"executing command: {command}")
    try:
        exit_code = executor.exec_command_in_dir(
            command,
            task.remote_work_dir,
            timeout_seconds=timeout_seconds,
            on_stdout_line=lambda line: _add_log(db, task_id, "INFO", line),
            on_stderr_line=lambda line: _add_log(db, task_id, "ERROR", line),
        )
    except SSHCommandTimeoutError as exc:
        _add_log(db, task_id, "ERROR", f"command timed out after {exc.timeout_seconds} seconds")
        task.status = "FAILED"
        task.exit_code = None
        task.end_time = datetime.utcnow()
        task.error_message = f"command timed out after {exc.timeout_seconds} seconds"
        db.commit()
        return

    _add_log(db, task_id, "SYSTEM", f"command exited with code {exit_code}")

    task.exit_code = exit_code
    task.end_time = datetime.utcnow()
    if exit_code == 0:
        task.status = "SUCCESS"
        task.error_message = None
    else:
        task.status = "FAILED"
        task.error_message = f"command exited with code {exit_code}"
    db.commit()


def _build_test_command(file_name: str) -> str:
    return f"bash ./{Path(file_name).name}"


def _build_stress_command(task: Task) -> str:
    if not task.file_name:
        raise TaskRunnerError("task file_name is empty")

    params = task.params or {}
    duration_seconds = params.get("duration_seconds")
    if not isinstance(duration_seconds, int):
        raise TaskRunnerError("stress duration_seconds is invalid")
    if duration_seconds <= 0:
        raise TaskRunnerError("stress duration_seconds must be greater than 0")
    if duration_seconds > 3600:
        raise TaskRunnerError("stress duration_seconds must be less than or equal to 3600")

    return f"./{Path(task.file_name).name} {duration_seconds}"


def _resolve_command_timeout(task: Task) -> int:
    if task.task_type == "stress":
        params = task.params or {}
        duration_seconds = params.get("duration_seconds")
        if not isinstance(duration_seconds, int):
            raise TaskRunnerError("stress duration_seconds is invalid")
        return max(duration_seconds + 300, 300)
    if task.task_type == "test":
        return 120
    raise TaskRunnerError(f"execution is not supported for task_type: {task.task_type}")


def _should_chmod(local_path: Path) -> bool:
    return local_path.suffix.lower() in {".sh", ".py"}


def _mark_task_started(db, task: Task) -> None:
    if task.start_time is None:
        task.start_time = datetime.utcnow()
        db.commit()


def _add_log(db, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()


def _set_status(db, task: Task, status: str) -> None:
    task.status = status
    db.commit()


def _fail_task(db, task_id: str, message: str) -> None:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        return
    task.status = "FAILED"
    task.error_message = message[:500]
    task.end_time = datetime.utcnow()
    db.commit()
    db.add(TaskLog(task_id=task_id, level="ERROR", message=message[:1000]))
    db.commit()
