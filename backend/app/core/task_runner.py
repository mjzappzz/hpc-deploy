from datetime import datetime
from pathlib import Path

from app.core.script_library import get_library_file_record, resolve_library_path
from app.core.script_validator import ScriptValidationError
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError, shell_quote
from app.db.database import SessionLocal
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog

TASK_STATUSES = (
    "PENDING",
    "CONNECTING",
    "PREPARING",
    "UPLOADING",
    "RUNNING",
    "CANCELING",
    "SUCCESS",
    "FAILED",
    "CANCELED",
)
UNFINISHED_TASK_STATUSES = (
    "PENDING",
    "CONNECTING",
    "PREPARING",
    "UPLOADING",
    "RUNNING",
    "CANCELING",
)
TERMINAL_TASK_STATUSES = ("SUCCESS", "FAILED", "CANCELED")
CANCELABLE_TASK_STATUSES = ("PENDING", "CONNECTING", "PREPARING", "UPLOADING", "RUNNING")
APPTAINER_REMOTE_DIR_SUFFIX = "/hpcdeploy/apptainer"
MPI_ENV_TEST_FILENAME = "mpi_env_test.sh"
MPI_ONEAPI_FILENAME = "install_oneapi_2022.sh"
MPI_OPENMPI_FILENAME = "install_openmpi_4.1.6_aocc_aocl.sh"
TEST_ALLOWED_FILENAMES = {"hello.sh", "sleep_60.sh"}
ALLOWED_MPI_FILENAMES = {
    MPI_ENV_TEST_FILENAME,
    MPI_ONEAPI_FILENAME,
    MPI_OPENMPI_FILENAME,
}
MPI_TASK_BLOCKED_MESSAGE = (
    "当前阶段只允许执行 mpi_env_test.sh、install_oneapi_2022.sh、"
    "install_openmpi_4.1.6_aocc_aocl.sh。"
)
STDERR_WARN_PATTERNS = (
    "WARNING:",
    "warning:",
    "Use with caution in scripts",
    "apt does not have a stable CLI interface",
)
PID_FILE_NAME = ".hpcdeploy.pid"
CANCELED_EXIT_CODE = -15


def run_task_stage8b(task_id: str) -> None:
    db = SessionLocal()
    executor = SSHExecutor()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None:
            return
        if _is_task_canceled(task):
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
        _ensure_task_not_canceled(db, task)
        _add_log(db, task_id, "SYSTEM", "connected")

        remote_home = executor.get_remote_home()
        _ensure_task_not_canceled(db, task)
        _add_log(db, task_id, "SYSTEM", f"remote HOME detected: {remote_home}")

        remote_dir = _resolve_remote_work_dir(task.task_type, remote_home)
        task.remote_work_dir = remote_dir
        db.commit()
        _ensure_task_not_canceled(db, task)
        _add_log(db, task_id, "SYSTEM", f"remote work dir resolved: {remote_dir}")

        remote_path = _build_remote_path(remote_dir, str(file_record["name"]))

        _set_status(db, task, "PREPARING")
        _mark_task_started(db, task)
        _ensure_task_not_canceled(db, task)
        _add_log(
            db,
            task_id,
            "SYSTEM",
            "creating remote directory" if task.task_type == "apptainer" else f"creating remote directory {remote_dir}",
        )
        executor.mkdir_p(remote_dir)

        _set_status(db, task, "UPLOADING")
        _ensure_task_not_canceled(db, task)
        _add_log(
            db,
            task_id,
            "SYSTEM",
            "uploading apptainer file" if task.task_type == "apptainer" else f"uploading {task.file_path}",
        )
        executor.upload_file(str(local_path), remote_path)
        _ensure_task_not_canceled(db, task)
        _add_log(db, task_id, "SYSTEM", f"uploaded to {remote_path}")

        if _should_chmod(local_path):
            _ensure_task_not_canceled(db, task)
            _add_log(db, task_id, "SYSTEM", "running chmod +x")
            executor.chmod(remote_path, 0o755)
            _ensure_task_not_canceled(db, task)
            _add_log(db, task_id, "SYSTEM", "chmod +x completed")

        if task.task_type == "test":
            _execute_command_task(db, executor, task, task_id, _build_test_command(task.file_name))
        elif task.task_type == "mpi":
            _execute_command_task(db, executor, task, task_id, _build_mpi_command(task.file_name))
        elif task.task_type == "stress":
            _execute_command_task(db, executor, task, task_id, _build_stress_command(task))
            db.refresh(task)
            if task.status == "CANCELED":
                _add_log(db, task_id, "SYSTEM", "task canceled, skip artifact collection")
            elif task.remote_work_dir:
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
    except TaskCanceledError:
        pass
    except Exception:
        _fail_task(db, task_id, "task preparation failed")
    finally:
        executor.close()
        db.close()


class TaskRunnerError(Exception):
    pass


class TaskCanceledError(Exception):
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
    if task.task_type == "test" and file_name not in TEST_ALLOWED_FILENAMES:
        raise TaskRunnerError("当前阶段只允许执行 hello.sh、sleep_60.sh。")
    if task.task_type == "mpi" and file_name not in ALLOWED_MPI_FILENAMES:
        raise TaskRunnerError(MPI_TASK_BLOCKED_MESSAGE)
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
    _ensure_task_not_canceled(db, task)
    _set_status(db, task, "RUNNING")
    pid_file_path = _build_remote_pid_file_path(task.remote_work_dir)
    remote_command = _build_remote_execution_command(command, pid_file_path)
    _add_log(db, task_id, "SYSTEM", f"command timeout set to {timeout_seconds} seconds")
    _add_log(db, task_id, "SYSTEM", f"remote pid file: {pid_file_path}")
    _add_log(db, task_id, "SYSTEM", f"executing command: {command}")
    try:
        exit_code = executor.exec_command_in_dir(
            remote_command,
            task.remote_work_dir,
            timeout_seconds=timeout_seconds,
            on_stdout_line=lambda line: _add_log(db, task_id, "INFO", line),
            on_stderr_line=lambda line: _add_log(db, task_id, _classify_stderr_level(line), line),
        )
    except SSHCommandTimeoutError as exc:
        db.refresh(task)
        if task.status == "CANCELING":
            task.status = "CANCELED"
            task.exit_code = CANCELED_EXIT_CODE
            task.end_time = datetime.utcnow()
            task.error_message = "canceled by user"
            db.commit()
            return
        _add_log(db, task_id, "ERROR", f"command timed out after {exc.timeout_seconds} seconds")
        task.status = "FAILED"
        task.exit_code = None
        task.end_time = datetime.utcnow()
        task.error_message = f"command timed out after {exc.timeout_seconds} seconds"
        db.commit()
        return

    _add_log(db, task_id, "SYSTEM", f"command exited with code {exit_code}")

    db.refresh(task)
    if task.status == "CANCELED":
        return
    task.exit_code = exit_code
    task.end_time = datetime.utcnow()
    if task.status == "CANCELING":
        task.status = "CANCELED"
        task.exit_code = CANCELED_EXIT_CODE
        task.error_message = "canceled by user"
    elif exit_code == 0:
        task.status = "SUCCESS"
        task.error_message = None
    else:
        task.status = "FAILED"
        task.error_message = f"command exited with code {exit_code}"
        _add_log(db, task_id, "ERROR", f"command failed with exit code {exit_code}")
    db.commit()


def _build_test_command(file_name: str) -> str:
    return f"bash ./{Path(file_name).name}"


def _build_mpi_command(file_name: str | None) -> str:
    if not file_name:
        raise TaskRunnerError("task file_name is empty")
    script_name = Path(file_name).name
    if script_name not in ALLOWED_MPI_FILENAMES:
        raise TaskRunnerError(MPI_TASK_BLOCKED_MESSAGE)
    return f"bash ./{script_name}"


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
    if task.task_type == "mpi":
        script_name = Path(task.file_name or "").name
        if script_name == MPI_ENV_TEST_FILENAME:
            return 120
        if script_name == MPI_ONEAPI_FILENAME:
            return 14400
        if script_name == MPI_OPENMPI_FILENAME:
            return 21600
        raise TaskRunnerError(MPI_TASK_BLOCKED_MESSAGE)
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


def _classify_stderr_level(message: str) -> str:
    if any(pattern in message for pattern in STDERR_WARN_PATTERNS):
        return "WARN"
    return "STDERR"


def _build_remote_execution_command(command: str, pid_file_path: str) -> str:
    inner_command = f"printf '%s' $$ > {shell_quote(pid_file_path)}; exec {command}"
    return f"setsid --wait bash -lc {shell_quote(inner_command)}"


def _build_remote_pid_file_path(remote_work_dir: str | None) -> str:
    if not remote_work_dir:
        raise TaskRunnerError("task remote_work_dir is empty")
    return f"{remote_work_dir.rstrip('/')}/{PID_FILE_NAME}"


def _is_task_canceled(task: Task) -> bool:
    return task.status in {"CANCELING", "CANCELED"}


def _ensure_task_not_canceled(db, task: Task) -> None:
    db.refresh(task)
    if task.status == "CANCELED":
        raise TaskCanceledError()
    if task.status == "CANCELING":
        _mark_task_canceled(db, task, "task canceled before remote execution")
        raise TaskCanceledError()


def _mark_task_canceled(db, task: Task, message: str) -> None:
    if task.status == "CANCELED":
        return
    task.status = "CANCELED"
    task.end_time = datetime.utcnow()
    task.exit_code = CANCELED_EXIT_CODE
    task.error_message = message
    db.commit()
    _add_log(db, task.task_id, "SYSTEM", message)


def _set_status(db, task: Task, status: str) -> None:
    task.status = status
    db.commit()


def _fail_task(db, task_id: str, message: str) -> None:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        return
    if task.status == "CANCELING":
        task.status = "CANCELED"
        task.exit_code = CANCELED_EXIT_CODE
        task.end_time = datetime.utcnow()
        task.error_message = "canceled by user"
        db.commit()
        return
    if task.status == "CANCELED":
        return
    task.status = "FAILED"
    task.error_message = message[:500]
    task.end_time = datetime.utcnow()
    db.commit()
    db.add(TaskLog(task_id=task_id, level="ERROR", message=message[:1000]))
    db.commit()
