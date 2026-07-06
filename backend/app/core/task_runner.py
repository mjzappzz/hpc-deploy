from datetime import datetime, timedelta
from pathlib import Path
import os
import re
import threading
from time import monotonic

from app.core.report_summary import schedule_report_summary_generation
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
TASK_LEASE_SECONDS = 600
STRESS_STARTUP_TIMEOUT_SECONDS = 300
STRESS_FATAL_LOG_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"nvidia-smi not found", re.IGNORECASE), "GPU stress failed before start: nvidia-smi not found"),
    (re.compile(r"未检测到 NVIDIA GPU", re.IGNORECASE), "GPU stress failed before start: no NVIDIA GPU detected"),
    (re.compile(r"nvcc not found.*无法编译 gpu-burn|nvcc not found", re.IGNORECASE), "GPU stress failed before start: nvcc not found"),
    (re.compile(r"gpu-burn build failed", re.IGNORECASE), "GPU stress failed before start: gpu-burn build failed"),
    (re.compile(r"GitHub clone failed", re.IGNORECASE), "GPU stress failed before start: gpu-burn source download failed"),
    (re.compile(r"ERROR:\s*stress-ng not found", re.IGNORECASE), "CPU/memory stress failed before start: stress-ng not found"),
    (re.compile(r"ERROR:\s*python3 not found", re.IGNORECASE), "stress failed before start: python3 not found"),
    (re.compile(r"ERROR:\s*python3-openpyxl not found|python3-openpyxl not found", re.IGNORECASE), "stress failed before start: python3-openpyxl not found"),
    (re.compile(r"\[ERROR\]\s*Unsupported OS", re.IGNORECASE), "stress failed before start: unsupported OS"),
    (re.compile(r"\[ERROR\]\s*请使用 root 用户运行|请使用 root 用户运行", re.IGNORECASE), "stress failed before start: root user is required"),
)


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
            _execute_stress_async(db, executor, task, task_id, _build_stress_command(task))
            # _execute_stress_async 内部包含：
            #   - nohup 后台启动脚本
            #   - 轮询远程日志和报告
            #   - 报告生成后自动 artifact collection + 状态更新
            #   返回时任务已到达终态或不用额外处理
            db.refresh(task)
            if task.status not in TERMINAL_TASK_STATUSES:
                _add_log(db, task_id, "ERROR", f"stress runner returned before terminal status: {task.status}")
                _fail_task(db, task_id, "stress runner returned before terminal status")
        elif task.task_type == "apptainer":
            _add_log(db, task_id, "SYSTEM", "apptainer distribution completed, file was uploaded but not executed")
            task.status = "SUCCESS"
            task.exit_code = 0
            task.end_time = datetime.utcnow()
            task.error_message = None
            db.commit()
            _broadcast_done_safe(task_id, "SUCCESS")
        else:
            _add_log(db, task_id, "SYSTEM", "stage 8B completed, script was uploaded but not executed")
            task.status = "SUCCESS"
            task.exit_code = 0
            task.end_time = datetime.utcnow()
            task.error_message = None
            db.commit()
            _broadcast_done_safe(task_id, "SUCCESS")
    except (TaskRunnerError, SSHExecutorError, ScriptValidationError) as exc:
        _fail_task(db, task_id, str(exc))
    except TaskCanceledError:
        pass
    except Exception as _exc:
        _add_log(db, task_id, "ERROR", f"task preparation failed: {type(_exc).__name__}: {_exc}")
        import traceback
        _tb = traceback.format_exc()[:500]
        _add_log(db, task_id, "ERROR", f"traceback: {_tb}")
        _fail_task(db, task_id, f"task preparation failed")
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

    # ── stress 早期 recovery：duration+grace 后主动探测远端报告 ──
    _stress_grace = 0
    _stress_dur = 0
    _stress_cmd_start = monotonic()
    if task.task_type == "stress":
        _p = task.params or {}
        _d = _p.get("duration_seconds", 0)
        if isinstance(_d, int) and _d > 0:
            _stress_dur = _d
            _stress_grace = _calculate_stress_grace(_d)
    _early_stop = False

    def _stress_tick() -> bool:
        nonlocal _early_stop
        if _early_stop:
            return True
        if _stress_grace <= 0:
            return False
        if monotonic() - _stress_cmd_start > _stress_dur + _stress_grace:
            _early_stop = True
            _add_log(db, task_id, "SYSTEM",
                     f"early recovery: elapsed > duration {_stress_dur}s + grace {_stress_grace}s")
            return True
        return False

    try:
        exit_code = executor.exec_command_in_dir(
            remote_command,
            task.remote_work_dir,
            timeout_seconds=timeout_seconds,
            on_stdout_line=lambda line: _add_log(db, task_id, "INFO", line),
            on_stderr_line=lambda line: _add_log(db, task_id, _classify_stderr_level(line), line),
            on_tick=_stress_tick,
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
        _stage_hint = ""
        if task.task_type == "stress":
            _stage_hint = " (stress script may be stuck at stress-ng or report stage)"
        _add_log(db, task_id, "ERROR", f"command timed out after {exc.timeout_seconds} seconds{_stage_hint}")
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
    if status in TERMINAL_TASK_STATUSES:
        schedule_report_summary_generation(task_id)
    try:
        ws_manager.broadcast_status_sync(task_id, status)
        ws_manager.broadcast_done_sync(task_id, status)
    except Exception:
        pass


def _broadcast_status_safe(task_id: str, status: str) -> None:
    """仅广播状态更新（不广播 done），用于轮询期间保持前端刷新。"""
    try:
        ws_manager.broadcast_status_sync(task_id, status)
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


def _exec_with_reconnect(executor: SSHExecutor, cmd: str) -> str | None:
    """Execute exec_simple with one reconnection attempt on failure.

    Returns stripped stdout on success, None if both attempts fail.
    Logs are not written — caller handles contextual logging.
    """
    for attempt in range(2):
        try:
            return executor.exec_simple(cmd)
        except SSHExecutorError:
            if attempt == 0:
                try:
                    executor.reconnect()
                except SSHExecutorError:
                    return None
            else:
                return None
    return None


def _classify_stress_fatal_log(log_text: str) -> str | None:
    """Return a platform failure reason for startup/dependency fatal stress logs."""
    for pattern, reason in STRESS_FATAL_LOG_RULES:
        if pattern.search(log_text):
            return reason
    return None


def _extract_stress_exit_reason(log_text: str) -> str:
    fatal_reason = _classify_stress_fatal_log(log_text)
    if fatal_reason:
        return fatal_reason

    for line in reversed(log_text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if "[error]" in low or low.startswith("error:") or "not found" in low or "exit_code=" in low:
            return f"stress script exited before report generation: {stripped[:300]}"
    return "stress script exited before report generation, no report found"


def _classify_stress_startup_stall(log_text: str, elapsed: int) -> str | None:
    if elapsed < STRESS_STARTUP_TIMEOUT_SECONDS:
        return None
    lower_text = log_text.lower()
    if "[stage] stress_start" in lower_text:
        return None
    if "missing dependencies detected, installing" in lower_text:
        return (
            "stress failed before start: dependency installation did not finish "
            f"within {STRESS_STARTUP_TIMEOUT_SECONDS}s"
        )
    if "[stage] dependency_check_start" in lower_text and "[stage] dependency_check_done" not in lower_text:
        return (
            "stress failed before start: dependency check did not finish "
            f"within {STRESS_STARTUP_TIMEOUT_SECONDS}s"
        )
    if "gpu-burn not found or force rebuild, start building" in lower_text:
        return (
            "GPU stress failed before start: gpu-burn build did not finish "
            f"within {STRESS_STARTUP_TIMEOUT_SECONDS}s"
        )
    return None


def _is_remote_pid_alive(executor: SSHExecutor, pid_file: str) -> bool | None:
    command = (
        f"pid=$(cat {shell_quote(pid_file)} 2>/dev/null || true); "
        "case \"$pid\" in ''|*[!0-9]*) echo unknown; exit 0;; esac; "
        "if [ -d \"/proc/$pid\" ]; then echo alive; else echo dead; fi"
    )
    result = _exec_with_reconnect(executor, command)
    if result is None:
        return None
    state = result.strip().splitlines()[-1] if result.strip() else "unknown"
    if state == "alive":
        return True
    if state == "dead":
        return False
    return None


def _terminate_remote_pid_group(executor: SSHExecutor, pid_file: str) -> None:
    command = (
        f"pid=$(cat {shell_quote(pid_file)} 2>/dev/null || true); "
        "case \"$pid\" in ''|*[!0-9]*) exit 0;; esac; "
        "if [ ! -d \"/proc/$pid\" ]; then exit 0; fi; "
        "pgid=$(ps -p \"$pid\" -o pgid= 2>/dev/null | tr -d ' '); "
        "if [ -z \"$pgid\" ] || [ \"$pgid\" = 0 ]; then exit 0; fi; "
        "kill -TERM -\"$pgid\" 2>/dev/null || true; "
        "sleep 3; "
        "if ps --no-headers -g \"$pgid\" >/dev/null 2>&1; then "
        "  kill -KILL -\"$pgid\" 2>/dev/null || true; "
        "fi"
    )
    _exec_with_reconnect(executor, command)


def _fail_running_stress_task(db, task: Task, task_id: str, message: str) -> None:
    db.refresh(task)
    if task.status in ("CANCELED", "CANCELING", "SUCCESS"):
        return
    task.status = "FAILED"
    task.exit_code = None
    task.end_time = datetime.utcnow()
    task.error_message = message[:500]
    db.commit()
    _add_log(db, task_id, "ERROR", message[:1000])
    _broadcast_done_safe(task_id, "FAILED")


def _execute_stress_async(db, executor: SSHExecutor, task: Task, task_id: str, command: str) -> None:
    """后台启动 stress 脚本 + 轮询远端报告收尾。

    不阻塞等待 SSH channel 关闭，而是：
    1. nohup 后台启动脚本，保存 PID 到 .hpcdeploy.pid
    2. 定期轮询远程日志和报告文件
    3. 报告（xlsx/txt）生成后自动 artifact collection + 状态更新
    4. duration + grace 过后仍未生成报告则强制收尾
    """
    from time import sleep as _poll_sleep
    from app.core.artifact_collector import collect_artifacts

    params = task.params or {}
    duration_seconds = params.get("duration_seconds", 0)
    if not isinstance(duration_seconds, int) or duration_seconds <= 0:
        raise TaskRunnerError("stress duration_seconds is invalid")

    timeout_seconds, _ = calculate_stress_command_timeout(duration_seconds)
    grace = _calculate_stress_grace(duration_seconds)
    poll_interval = 10

    task.start_time = datetime.utcnow()
    db.commit()
    _ensure_task_not_canceled(db, task)
    _set_status(db, task, "RUNNING")

    pid_file = _build_remote_pid_file_path(task.remote_work_dir)
    log_file = shell_quote(f"{task.remote_work_dir.rstrip('/')}/task.log")
    work_dir = shell_quote(task.remote_work_dir)

    _add_log(db, task_id, "SYSTEM", f"stress async start: duration={duration_seconds}s grace={grace}s")
    _add_log(db, task_id, "SYSTEM", f"remote pid file: {pid_file}")

    # 后台启动脚本：完全 detach，写入 task.log，PID 写入 .hpcdeploy.pid。
    # 必须重定向 stdin/stdout/stderr，否则 Paramiko 可能一直等待远端 channel EOF。
    bg_cmd = (
        f"cd {work_dir} && "
        f"(setsid bash -lc {shell_quote(command)} > {log_file} 2>&1 < /dev/null "
        f"& echo $! > {shell_quote(pid_file)})"
    )
    try:
        executor.exec_simple(bg_cmd)
    except SSHExecutorError as exc:
        raise TaskRunnerError(f"failed to start stress async: {exc}")

    # 确认进程已启动：检查 PID 文件
    try:
        _pid_check = executor.exec_simple(
            f"test -f {shell_quote(pid_file)} && cat {shell_quote(pid_file)} || echo 0"
        ).strip()
        if _pid_check == "0":
            raise TaskRunnerError("stress async: PID file not found after start")
        _add_log(db, task_id, "SYSTEM", f"stress async: PID {_pid_check}")
    except SSHExecutorError:
        raise TaskRunnerError("stress async: failed to verify PID file")

    _add_log(db, task_id, "SYSTEM", "stress script started in background (async mode)")

    # ── 轮询循环 ──
    deadline = duration_seconds + grace
    elapsed = 0
    last_log_pos = 0
    full_log_text = ""

    while elapsed < deadline:
        _poll_sleep(poll_interval)
        elapsed += poll_interval

        # 1. 检查是否被取消
        db.refresh(task)
        if task.status in ("CANCELED", "CANCELING"):
            _add_log(db, task_id, "SYSTEM", "stress async: task canceled, stopping poll")
            return

        # 2. 拉取最新日志（含连接失败自动重连）
        _sz_raw = _exec_with_reconnect(executor, f"wc -c < {log_file} 2>/dev/null || echo 0")
        if _sz_raw is not None:
            _cur = int(_sz_raw.strip()) if _sz_raw.strip().isdigit() else 0
            if _cur > last_log_pos:
                _seg_raw = _exec_with_reconnect(
                    executor, f"tail -c +{last_log_pos + 1} {log_file} 2>/dev/null"
                )
                if _seg_raw:
                    full_log_text += _seg_raw
                    for _ln in _seg_raw.strip().split("\n"):
                        _ln = _ln.strip()
                        if _ln:
                            _add_log(db, task_id, "INFO", _ln)
                last_log_pos = _cur

        fatal_reason = _classify_stress_fatal_log(full_log_text)
        if fatal_reason:
            _add_log(db, task_id, "ERROR", f"stress async: fatal startup error detected: {fatal_reason}")
            _terminate_remote_pid_group(executor, pid_file)
            _fail_running_stress_task(db, task, task_id, fatal_reason)
            return

        startup_stall_reason = _classify_stress_startup_stall(full_log_text, elapsed)
        if startup_stall_reason:
            _add_log(db, task_id, "ERROR", f"stress async: startup stalled: {startup_stall_reason}")
            _terminate_remote_pid_group(executor, pid_file)
            _fail_running_stress_task(db, task, task_id, startup_stall_reason)
            return

        # 3. 检查报告是否生成（含连接失败自动重连）
        _rx_raw = _exec_with_reconnect(
            executor, f"ls {shell_quote(task.remote_work_dir)}/*report*.xlsx 2>/dev/null | head -1"
        )
        if _rx_raw:
            _rx = _rx_raw.strip()
            if _rx:
                _add_log(db, task_id, "SYSTEM", f"stress async: xlsx report found ({_rx})")
                downloaded = collect_artifacts(db, task_id, task.remote_work_dir, executor)
                db.refresh(task)
                if task.status not in ("CANCELED", "CANCELING", "SUCCESS"):
                    recovered = _attempt_stress_recovery(db, task_id, task)
                    if recovered:
                        _add_log(db, task_id, "SYSTEM", "stress async: completed via report detection")
                    else:
                        _add_log(
                            db,
                            task_id,
                            "ERROR",
                            "stress async: remote report detected but local artifact recovery failed",
                        )
                        task.status = "FAILED"
                        task.exit_code = None
                        task.end_time = datetime.utcnow()
                        task.error_message = (
                            "remote report detected but local artifact recovery failed"
                            if downloaded else
                            "remote report detected but no report artifact was collected"
                        )
                        db.commit()
                        _broadcast_done_safe(task_id, "FAILED")
                return

        pid_alive = _is_remote_pid_alive(executor, pid_file)
        if pid_alive is False:
            reason = _extract_stress_exit_reason(full_log_text)
            _add_log(db, task_id, "ERROR", f"stress async: remote script exited without report: {reason}")
            try:
                collect_artifacts(db, task_id, task.remote_work_dir, executor)
            except Exception:
                pass
            if not _attempt_stress_recovery(db, task_id, task):
                _fail_running_stress_task(db, task, task_id, reason)
            return

        # 4. 保持 RUNNING 广播（前端进度可见）
        _broadcast_status_safe(task_id, "RUNNING")

    # ── deadline 超时 ──
    _add_log(db, task_id, "SYSTEM", f"stress async: deadline exceeded ({deadline}s), final check")
    db.refresh(task)
    if task.status not in ("CANCELED", "CANCELING", "SUCCESS"):
        try:
            collect_artifacts(db, task_id, task.remote_work_dir, executor)
        except Exception:
            pass
        if not _attempt_stress_recovery(db, task_id, task):
            task.status = "FAILED"
            task.exit_code = None
            task.end_time = datetime.utcnow()
            task.error_message = f"stress deadline exceeded ({deadline}s), no report found"
            db.commit()
            _broadcast_done_safe(task_id, "FAILED")


def _attempt_stress_recovery(db, task_id: str, task: Task) -> bool:
    """检查 stress 报告 artifact 并根据产物结果更新任务状态。

    ── 核心原则 ──
    平台任务状态 task.status = "脚本有没有跑完 / 产物有没有生成"。
    压测结果（PASS/FAIL）是报告内的判断，不直接决定 task.status。

    ── 判定规则 ──
    1. xlsx 已生成 → 产物已完备 → task = SUCCESS
       - txt 同步存在 + PASS → SUCCESS，无特殊说明
       - txt 同步存在 + FAIL → SUCCESS，error_message 记录"压测结果为 FAIL"
       - txt 不存在 → SUCCESS，error_message 记录"xlsx 已生成但未找到 txt 摘要"
    2. xlsx 不存在，txt 存在 → 同规则（可能 txt-only 场景）
    3. 无任何报告 → 返回 False（调用方可尝试远端重取）

    Returns:
        True 已尝试恢复，False 无报告可解析。
    """
    from pathlib import Path

    artifacts_dir = Path(__file__).resolve().parents[2] / "data" / "artifacts" / task_id
    if not artifacts_dir.is_dir():
        return False

    xlsx_files = list(artifacts_dir.glob("*report*.xlsx"))
    txt_reports = list(artifacts_dir.glob("*report*.txt"))

    has_xlsx = bool(xlsx_files)
    has_txt = bool(txt_reports)

    if not has_xlsx and not has_txt:
        return False

    # 解析 txt（如果存在）
    report_result: str | None = None  # "PASS" | "FAIL" | None
    if has_txt:
        content = txt_reports[0].read_text(errors="replace", encoding="utf-8")
        if "测试结果              : PASS" in content:
            report_result = "PASS"
        elif "测试结果              : FAIL" in content:
            report_result = "FAIL"

    # 构建诊断信息
    detail_parts: list[str] = []
    if has_xlsx:
        detail_parts.append(f"xlsx: {xlsx_files[0].name}")
    if report_result:
        detail_parts.append(f"report: {report_result}")

    # 根据报告产物更新 task 状态
    if task.status != "SUCCESS":
        task.status = "SUCCESS"
        task.exit_code = 0
        task.end_time = datetime.utcnow()

        if report_result == "FAIL":
            task.error_message = f"报告已生成，压测结果为 FAIL，请查看报告（{' '.join(detail_parts)}）"
        elif not has_txt and has_xlsx:
            task.error_message = f"xlsx 已生成，未找到 txt 结果摘要（{xlsx_files[0].name}）"
        else:
            task.error_message = None

        db.commit()
        _broadcast_done_safe(task_id, "SUCCESS")

    msg = f"stress recovery: completed with {' '.join(detail_parts)}"
    _add_log(db, task_id, "SYSTEM", msg)
    return True


def _connect_recovery_executor(task: Task) -> SSHExecutor | None:
    """创建一个新的 SSH 连接到任务的目标服务器，用于故障恢复。

    当主执行器的连接已断开时（如 command timeout 后 connection dropped），
    用此函数重建连接去远端取 artifact。
    """
    from app.db.database import SessionLocal
    from app.models.server import Server

    db = SessionLocal()
    try:
        server = db.get(Server, task.server_id)
        if server is None:
            return None
        fresh = SSHExecutor()
        fresh.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )
        return fresh
    except Exception:
        return None
    finally:
        db.close()


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


def _calculate_stress_grace(duration_seconds: int) -> int:
    """stress 早期 recovery 的宽限时间。

    在 duration 到期后额外等待的时间，超过此时间仍未结束则主动探测远端报告。
    远小于外层 timeout buffer，用于提前 recovery。
    """
    if duration_seconds <= 0:
        return 120
    if duration_seconds <= 600:       # ≤ 10 分钟
        return 120
    if duration_seconds <= 3600:      # ≤ 1 小时
        return 300
    return 600                         # > 1 小时


def _should_chmod(local_path: Path) -> bool:
    return local_path.suffix.lower() in {".sh", ".py"}


def _mark_task_started(db, task: Task) -> None:
    if task.start_time is None:
        task.start_time = datetime.utcnow()
        _touch_task_heartbeat(task)
        db.commit()


def _add_log(db, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is not None and task.status in UNFINISHED_TASK_STATUSES:
        _touch_task_heartbeat(task)
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


def _current_worker_id() -> str:
    return f"{os.uname().nodename}:{os.getpid()}:{threading.get_ident()}"


def _touch_task_heartbeat(task: Task) -> None:
    now = datetime.utcnow()
    task.last_heartbeat = now
    task.worker_id = _current_worker_id()
    task.lease_expire_time = now + timedelta(seconds=TASK_LEASE_SECONDS)


def _clear_task_lease(task: Task) -> None:
    task.worker_id = None
    task.lease_expire_time = None


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
    _clear_task_lease(task)
    db.commit()
    _add_log(db, task.task_id, "SYSTEM", message)
    schedule_report_summary_generation(task.task_id)


def _set_status(db, task: Task, status: str) -> None:
    task.status = status
    if status in UNFINISHED_TASK_STATUSES:
        _touch_task_heartbeat(task)
    else:
        _clear_task_lease(task)
    db.commit()
    if status in TERMINAL_TASK_STATUSES:
        schedule_report_summary_generation(task.task_id)
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
        _clear_task_lease(task)
        final_status = "CANCELED"
        db.commit()
    elif task.status != "CANCELED":
        task.status = "FAILED"
        task.error_message = message[:500]
        task.end_time = datetime.utcnow()
        _clear_task_lease(task)
        final_status = "FAILED"
        db.commit()
        db.add(TaskLog(task_id=task_id, level="ERROR", message=message[:1000]))
        db.commit()
    if final_status:
        schedule_report_summary_generation(task_id)
        try:
            ws_manager.broadcast_status_sync(task_id, final_status)
            ws_manager.broadcast_done_sync(task_id, final_status)
        except Exception:
            pass
