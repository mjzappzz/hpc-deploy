from datetime import datetime
from pathlib import Path
import re

from app.core.script_library import get_library_file_record, resolve_library_path
from app.core.script_validator import ScriptValidationError
from app.core.ssh_executor import SSHCommandTimeoutError, SSHExecutor, SSHExecutorError, shell_quote
from app.core.ws_manager import ws_manager
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

        remote_dir = _resolve_remote_work_dir(task.task_type, remote_home, task.file_name)
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

        # ── Apptainer overwrite check ──
        if task.task_type == "apptainer":
            overwrite = task.params.get("overwrite", True) if task.params else True
            test_cmd = f"test -f {shell_quote(remote_path)}"
            exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
            file_exists = (exit_code == 0)
            if file_exists:
                if not overwrite:
                    _add_log(db, task_id, "ERROR", f"remote file exists and overwrite disabled: {remote_path}")
                    raise TaskRunnerError(f"remote file already exists: {remote_path}")
                _add_log(db, task_id, "SYSTEM", f"remote file exists, overwrite enabled: {remote_path}")
            else:
                _add_log(db, task_id, "SYSTEM", f"remote file not found, will upload: {remote_path}")
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

        if task.task_type == "script":
            _execute_command_task(db, executor, task, task_id, f"bash ./{Path(task.file_name or 'script').name}")
        elif task.task_type == "stress":
            _execute_command_task(db, executor, task, task_id, _build_stress_command(task))
            db.refresh(task)
            if task.status == "CANCELED":
                _add_log(db, task_id, "SYSTEM", "task canceled, skip artifact collection")
            elif task.remote_work_dir:
                try:
                    from app.core.artifact_collector import collect_artifacts

                    downloaded = collect_artifacts(db, task_id, task.remote_work_dir, executor)

                    # ── 超时恢复：command timeout 但 xlsx 已生成且 report PASS → 升级为 SUCCESS
                    db.refresh(task)
                    if task.status == "FAILED" and task.error_message and "timed out" in task.error_message:
                        _attempt_timeout_recovery(db, task_id, task, downloaded)
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
    physical = record["physical_category"]
    if task_type == "script":
        # "script" type accepts any non-stress, non-apptainer script
        if physical in ("stress", "apptainer"):
            raise TaskRunnerError("script task_type only allows non-stress, non-apptainer scripts")
    elif physical != task_type:
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


def _resolve_remote_work_dir(task_type: str | None, remote_home: str, file_name: str | None = None) -> str:
    if not task_type:
        raise TaskRunnerError("task type is empty")
    base_home = remote_home.rstrip("/")
    if task_type == "apptainer":
        return f"{base_home}{APPTAINER_REMOTE_DIR_SUFFIX}"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dir_name = build_remote_work_dir_name(task_type, file_name, timestamp)
    return f"{base_home}/hpcdeploy/tasks/{task_type}/{dir_name}"


def sanitize_dir_prefix(value: str) -> str:
    """Sanitize a string for use as a directory name prefix.

    Rules:
    1. Only allow a-z, A-Z, 0-9, _, -
    2. Other characters replaced with _
    3. Consecutive _ merged into one
    4. Leading and trailing _ removed
    5. Max length 80
    6. Empty fallback: "task"
    """
    if not value:
        return "task"
    result = re.sub(r'[^a-zA-Z0-9_-]', '_', value)
    result = re.sub(r'_+', '_', result)
    result = result.strip('_')
    result = result[:80]
    return result or "task"


def build_remote_work_dir_name(task_type: str, file_name: str | None, timestamp: str) -> str:
    """Build a human-readable remote work directory name.

    For stress tasks, derives prefix from the script file name
    (e.g. cpu_mem_stress_report.sh → cpu_mem_stress).
    For script tasks, uses the sanitized script name as prefix.
    For apptainer tasks, the caller returns early so this is only
    a fallback.

    Returns:
        str: Directory name like "cpu_mem_stress_20260626-091411"
    """
    if not file_name:
        return f"{task_type}_{timestamp}"

    # Strip known extensions
    name = file_name
    for ext in ('.sh', '.bash', '.py', '.sif'):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break

    # For stress scripts, strip trailing _report so
    # "cpu_mem_stress_report" becomes "cpu_mem_stress"
    if task_type == "stress":
        if name.endswith('_report'):
            name = name[:-len('_report')]

    prefix = sanitize_dir_prefix(name)
    return f"{prefix}_{timestamp}"


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
    if task.task_type == "stress":
        params = task.params or {}
        dur = params.get("duration_seconds", 0)
        if isinstance(dur, int) and dur > 0:
            _, _buf = calculate_stress_command_timeout(dur)
            _add_log(db, task_id, "SYSTEM", f"stress duration seconds: {dur}")
            _add_log(db, task_id, "SYSTEM", f"stress timeout buffer seconds: {_buf}")
            _add_log(db, task_id, "SYSTEM", f"command timeout seconds: {timeout_seconds} (stress duration {dur} + buffer {_buf})")
        else:
            _add_log(db, task_id, "SYSTEM", f"command timeout seconds: {timeout_seconds}")
    else:
        _add_log(db, task_id, "SYSTEM", f"command timeout seconds: {timeout_seconds}")
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
            _broadcast_done_safe(task_id, "CANCELED")
            return
        _add_log(db, task_id, "ERROR", f"command timed out after {exc.timeout_seconds} seconds")
        task.status = "FAILED"
        task.exit_code = None
        task.end_time = datetime.utcnow()
        task.error_message = f"command timed out after {exc.timeout_seconds} seconds"
        db.commit()
        _broadcast_done_safe(task_id, "FAILED")
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
    _broadcast_done_safe(task_id, task.status)


def _broadcast_done_safe(task_id: str, status: str) -> None:
    try:
        ws_manager.broadcast_status_sync(task_id, status)
        ws_manager.broadcast_done_sync(task_id, status)
    except Exception:
        pass


def _build_stress_command(task: Task) -> str:
    if not task.file_name:
        raise TaskRunnerError("task file_name is empty")

    params = task.params or {}
    duration_seconds = params.get("duration_seconds")
    if not isinstance(duration_seconds, int):
        raise TaskRunnerError("stress duration_seconds is invalid")

    script_name = Path(task.file_name).name
    interval = params.get("interval_seconds", 2)

    # Build env var prefix from additional params (memory_percent, workers, etc.)
    env_vars: list[str] = []

    if script_name == "cpu_mem_stress_report.sh":
        if "memory_percent" in params:
            env_vars.append(f"MEMORY_PERCENT={params['memory_percent']}")
        if "workers" in params:
            env_vars.append(f"WORKERS={params['workers']}")

    elif script_name == "disk_stress_report.sh":
        if "disk_file_size" in params:
            env_vars.append(f"TEST_FILE_SIZE={params['disk_file_size']}")
        if "disk_path" in params:
            env_vars.append(f"TEST_DIR={params['disk_path']}")
        if "disk_test_dir" in params:
            dtd = params["disk_test_dir"]
            if dtd:
                env_vars.append(f"DISK_TEST_DIR={shell_quote(dtd)}")
        if "workers" in params:
            env_vars.append(f"WORKERS={params['workers']}")

    elif script_name == "gpu_stress_report.sh":
        gpu_ids = params.get("gpu_ids")
        if gpu_ids and gpu_ids != "all":
            env_vars.append(f"CUDA_VISIBLE_DEVICES={gpu_ids}")
        if "gpu_memory_percent" in params:
            env_vars.append(f"GPU_MEMORY_PERCENT={params['gpu_memory_percent']}")
        if "gpu_backend" in params:
            env_vars.append(f"GPU_BACKEND={params['gpu_backend']}")

    env_prefix = " ".join(env_vars)
    if env_prefix:
        return f"{env_prefix} ./{script_name} {duration_seconds} {interval}"
    return f"./{script_name} {duration_seconds} {interval}"


def _attempt_timeout_recovery(db, task_id: str, task: Task, downloaded_files: list[str]) -> None:
    """After command timeout, check if stress report artifacts exist and mark SUCCESS.

    If the txt report exists locally (downloaded from remote) and contains
    'Result : PASS', the stress test itself completed — only report generation
    (xlsx) or cleanup was slow.  Upgrade to SUCCESS so the user sees a green
    result instead of a misleading FAILED caused by platform timeout.
    """
    from pathlib import Path

    artifacts_dir = Path(__file__).resolve().parents[2] / "data" / "artifacts" / task_id
    if not artifacts_dir.is_dir():
        _add_log(db, task_id, "SYSTEM", "timeout recovery skipped: no artifact directory")
        return

    # Find any *report*.txt file
    txt_reports = list(artifacts_dir.glob("*report*.txt"))
    if not txt_reports:
        _add_log(db, task_id, "ERROR", "timeout recovery: no report txt found among artifacts")
        return

    txt_report = txt_reports[0]
    content = txt_report.read_text(errors="replace", encoding="utf-8")

    has_pass = "测试结果              : PASS" in content
    has_fail = "测试结果              : FAIL" in content

    if has_pass:
        # Check if xlsx also exists
        xlsx_files = list(artifacts_dir.glob("*report*.xlsx"))
        if xlsx_files:
            _add_log(db, task_id, "SYSTEM", f"timeout recovery: xlsx artifact found after timeout: {xlsx_files[0].name}")
        _add_log(db, task_id, "SYSTEM", "timeout recovery: report shows PASS, upgrading to SUCCESS")
        task.status = "SUCCESS"
        task.exit_code = 0
        task.error_message = "command timeout occurred after report generated, treated as success"
        task.end_time = datetime.utcnow()
        db.commit()
        _broadcast_done_safe(task_id, "SUCCESS")
    elif has_fail:
        _add_log(db, task_id, "SYSTEM", "timeout recovery: report shows FAIL, keeping FAILED status")
    else:
        _add_log(db, task_id, "ERROR", f"timeout recovery: could not parse test result from {txt_report.name}")


def _resolve_command_timeout(task: Task) -> int:
    if task.task_type == "stress":
        params = task.params or {}
        duration_seconds = params.get("duration_seconds")
        if not isinstance(duration_seconds, int):
            raise TaskRunnerError("stress duration_seconds is invalid")
        timeout_seconds, _ = calculate_stress_command_timeout(duration_seconds)
        return timeout_seconds
    if task.task_type == "script":
        return 3600
    if task.task_type == "apptainer":
        return 300
    raise TaskRunnerError(f"execution is not supported for task_type: {task.task_type}")


def calculate_stress_command_timeout(duration_seconds: int) -> tuple[int, int]:
    """Calculate command timeout for stress tasks with appropriate buffer.

    stress duration is the user-requested test runtime; command timeout is the
    platform's protective ceiling.  The timeout MUST exceed the stress duration
    to allow for report generation (xlsx/txt), monitoring CSV collation,
    subprocess cleanup, error log review, and final PASS/FAILED output.
    Do NOT treat command timeout as a substitute for stress duration.

    Buffer tiers (conservative):
      ≤ 1 h    → 1800 s (30 min)
      < 12 h   → 3600 s ( 1 h)
      ≥ 12 h   → 7200 s ( 2 h)

    Returns:
        tuple[int, int]: (timeout_seconds, buffer_seconds)
    """
    if duration_seconds <= 0:
        return 3600, 0

    if duration_seconds <= 3600:
        buffer_seconds = 1800
    elif duration_seconds < 43200:
        buffer_seconds = 3600
    else:
        buffer_seconds = 7200

    return duration_seconds + buffer_seconds, buffer_seconds


def _should_chmod(local_path: Path) -> bool:
    return local_path.suffix.lower() in {".sh", ".py"}


def _mark_task_started(db, task: Task) -> None:
    if task.start_time is None:
        task.start_time = datetime.utcnow()
        db.commit()


def _add_log(db, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()
    # Broadcast via WebSocket (best-effort)
    try:
        ws_manager.broadcast_log_sync(task_id, level, message)
    except Exception:
        pass


def _classify_stderr_level(message: str) -> str:
    if any(pattern in message for pattern in STDERR_WARN_PATTERNS):
        return "WARN"
    return "STDERR"


def _build_remote_execution_command(command: str, pid_file_path: str) -> str:
    # Move leading env var assignments before exec so that
    #   exec KEY=VALUE ./script.sh  →  KEY=VALUE exec ./script.sh
    env_part = ""
    cmd = command
    while True:
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*=\S+)\s*', cmd)
        if not m:
            break
        env_part += m.group(0)
        cmd = cmd[m.end():]

    if env_part:
        inner_command = f"printf '%s' $$ > {shell_quote(pid_file_path)}; {env_part}exec {cmd}"
    else:
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
    # Broadcast status via WebSocket (best-effort)
    try:
        ws_manager.broadcast_status_sync(task.task_id, status)
        if status in ("SUCCESS", "FAILED", "CANCELED"):
            ws_manager.broadcast_done_sync(task.task_id, status)
    except Exception:
        pass


def _fail_task(db, task_id: str, message: str) -> None:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        return
    final_status: str | None = None
    if task.status == "CANCELING":
        task.status = "CANCELED"
        task.exit_code = CANCELED_EXIT_CODE
        task.end_time = datetime.utcnow()
        task.error_message = "canceled by user"
        final_status = "CANCELED"
        db.commit()
    elif task.status != "CANCELED":
        task.status = "FAILED"
        task.error_message = message[:500]
        task.end_time = datetime.utcnow()
        final_status = "FAILED"
        db.commit()
        db.add(TaskLog(task_id=task_id, level="ERROR", message=message[:1000]))
        db.commit()
    if final_status:
        try:
            ws_manager.broadcast_status_sync(task_id, final_status)
            ws_manager.broadcast_done_sync(task_id, final_status)
        except Exception:
            pass
