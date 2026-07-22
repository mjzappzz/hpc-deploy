"""Rocky 9.4 NVIDIA .run driver installation task.

The task deliberately has its own runner: a mandatory reboot is an expected
state transition, not an SSH failure.  State is persisted in ``Task.params``
so a backend restart can resume waiting for the host or monitoring the remote
installer without launching it twice.
"""

from __future__ import annotations

import base64
import re
import threading
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep

from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.core.script_validator import BACKEND_ROOT
from app.core.ws_manager import ws_manager
from app.db.database import SessionLocal
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog

GPU_DRIVER_TASK_TYPE = "gpu_driver"
GPU_DRIVER_FILE_NAME = "nvidia-rocky9-driver.run"
GPU_DRIVER_PHASE_KEY = "gpu_driver_phase"
GPU_DRIVER_BOOT_ID_KEY = "gpu_driver_boot_id"
GPU_DRIVER_PHASE_INITIAL = "initial"
GPU_DRIVER_PHASE_WAITING_REBOOT = "waiting_reboot"
GPU_DRIVER_PHASE_INSTALLING = "installing"
GPU_DRIVER_WAIT_REBOOT_SECONDS = 1800
GPU_DRIVER_RECONNECT_INTERVAL_SECONDS = 10
GPU_DRIVER_UPLOAD_ROOT = BACKEND_ROOT / "data" / "gpu_driver_uploads"
GPU_DRIVER_LIBRARY_ROOT = BACKEND_ROOT / "data" / "gpu_driver_library"
GPU_DRIVER_LIBRARY_TYPES = {
    "geforce": "GeForce",
    "datacenter": "Data Center",
}
LEGACY_GPU_DRIVER_LIBRARY_REFS = {
    "geforce_580": ("geforce", "000000000000000000000001"),
    "datacenter_580": ("datacenter", "000000000000000000000002"),
}
_scheduled_retry_ids: set[str] = set()
_scheduled_retry_lock = threading.Lock()


class GpuDriverValidationError(ValueError):
    pass


def _optional_param_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_library_driver_filename(filename: str) -> str:
    """Return a safe NVIDIA Linux installer filename or raise a validation error."""
    name = Path(filename).name
    if name != filename or not re.fullmatch(r"NVIDIA-Linux-x86_64-[^/]+\.run", name):
        raise GpuDriverValidationError("driver file must match NVIDIA-Linux-x86_64-xxx.run")
    return name


def driver_version_from_filename(filename: str) -> str:
    name = validate_library_driver_filename(filename)
    return name.removeprefix("NVIDIA-Linux-x86_64-").removesuffix(".run")


def should_skip_existing_driver(*, nvidia_smi_available: bool, force_install: bool) -> bool:
    return nvidia_smi_available and not force_install


def should_reboot_for_gpu_driver(*, nouveau_loaded: bool, kernel_reboot_required: bool) -> bool:
    return nouveau_loaded or kernel_reboot_required


def resolve_gpu_driver_os_profile(os_info: str | None) -> str:
    normalized = (os_info or "").lower()
    if "rocky" in normalized and re.search(r"(?:^|[^0-9])9(?:\.[0-9]+)?(?:[^0-9]|$)", normalized):
        return "rocky9"
    for version, profile in (("20.04", "ubuntu20"), ("22.04", "ubuntu22"), ("24.04", "ubuntu24")):
        if "ubuntu" in normalized and version in normalized:
            return profile
    raise GpuDriverValidationError(f"unsupported GPU driver operating system: {os_info or 'not detected'}")


def list_library_drivers() -> list[dict[str, object]]:
    """List the versioned NVIDIA Linux driver library without fixed slots."""
    records: list[dict[str, object]] = []
    for driver_type, label in GPU_DRIVER_LIBRARY_TYPES.items():
        type_root = GPU_DRIVER_LIBRARY_ROOT / driver_type
        if not type_root.is_dir():
            continue
        for driver_dir in type_root.iterdir():
            if not re.fullmatch(r"[a-f0-9]{24}", driver_dir.name) or not driver_dir.is_dir():
                continue
            files = [path for path in driver_dir.iterdir() if path.is_file()]
            if len(files) != 1:
                continue
            path = files[0]
            try:
                filename = validate_library_driver_filename(path.name)
            except GpuDriverValidationError:
                continue
            records.append({
                "driver_id": driver_dir.name,
                "driver_type": driver_type,
                "label": label,
                "filename": filename,
                "size": path.stat().st_size,
                "uploaded_at": datetime.fromtimestamp(path.stat().st_mtime),
            })
    return sorted(records, key=lambda record: (record["uploaded_at"], record["filename"]), reverse=True)


def resolve_library_driver(driver_type: str, driver_id: str) -> Path:
    if driver_type not in GPU_DRIVER_LIBRARY_TYPES or not re.fullmatch(r"[a-f0-9]{24}", driver_id):
        raise GpuDriverValidationError("invalid NVIDIA driver library reference")
    directory = (GPU_DRIVER_LIBRARY_ROOT / driver_type / driver_id).resolve()
    expected_parent = (GPU_DRIVER_LIBRARY_ROOT / driver_type).resolve()
    if directory.parent != expected_parent or not directory.is_dir():
        raise GpuDriverValidationError("NVIDIA driver library entry not found")
    files = [path for path in directory.iterdir() if path.is_file()]
    if len(files) != 1:
        raise GpuDriverValidationError("NVIDIA driver library entry is invalid")
    validate_library_driver_filename(files[0].name)
    return files[0]


def resolve_uploaded_driver(upload_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{24}", upload_id):
        raise GpuDriverValidationError("invalid uploaded driver ID")
    path = (GPU_DRIVER_UPLOAD_ROOT / f"{upload_id}.run").resolve()
    if path.parent != GPU_DRIVER_UPLOAD_ROOT.resolve() or not path.is_file():
        raise GpuDriverValidationError("uploaded driver file not found")
    return path


def build_rocky9_pre_reboot_script(disable_nouveau: bool = True) -> str:
    nouveau_steps = """
echo '========== [5/6] 禁用 Nouveau =========='
sudo bash -c "echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf"
sudo bash -c "echo 'options nouveau modeset=0' >> /etc/modprobe.d/blacklist-nouveau.conf"
echo '========== [6/6] 重建 initramfs =========='
sudo dracut --force
""" if disable_nouveau else """
echo '========== [5/6] Nouveau 未加载，跳过禁用与重启 =========='
"""
    return """#!/usr/bin/env bash
set -euo pipefail
sudo -n true
echo '========== [1/6] 检查 NVIDIA 显卡 =========='
echo '========== [1/6] 安装构建依赖 =========='
sudo yum install -y epel-release
sudo yum install -y gcc make dkms elfutils-libelf-devel libglvnd-devel pciutils pkgconfig curl
echo '========== [2/6] 检查 NVIDIA 显卡 =========='
lspci | grep -i nvidia || { echo 'ERROR: 未检测到 NVIDIA GPU'; exit 20; }
echo '========== [3/6] 更新系统及内核 =========='
sudo yum update -y
echo '========== [4/6] 当前运行内核 =========='
uname -r
""" + nouveau_steps


def build_ubuntu_pre_reboot_script(disable_nouveau: bool = True) -> str:
    nouveau_steps = """
echo '========== [5/6] 禁用 Nouveau =========='
sudo bash -c "echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf"
sudo bash -c "echo 'options nouveau modeset=0' >> /etc/modprobe.d/blacklist-nouveau.conf"
echo '========== [6/6] 重建 initramfs =========='
sudo update-initramfs -u
""" if disable_nouveau else """
echo '========== [5/6] Nouveau 未加载，跳过禁用与重启 =========='
"""
    return """#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo -n true
echo '========== [1/6] 更新软件包索引 =========='
sudo apt-get update
echo '========== [2/6] 安装构建依赖与当前内核头文件 =========='
sudo apt-get install -y pkg-config libglvnd-dev build-essential dkms pciutils "linux-headers-$(uname -r)"
echo '========== [3/6] 检查 NVIDIA 显卡 =========='
lspci | grep -i nvidia || { echo 'ERROR: 未检测到 NVIDIA GPU'; exit 20; }
echo '========== [4/6] 当前运行内核 =========='
uname -r
""" + nouveau_steps


def installed_driver_matches_target(output: str, target_version: str | None) -> bool:
    """Return True only when every detected GPU reports the selected library version."""
    if not target_version:
        return False
    versions = [line.strip() for line in output.splitlines() if line.strip()]
    return bool(versions) and all(version == target_version for version in versions)


def build_rocky9_install_script() -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
driver_file='./{GPU_DRIVER_FILE_NAME}'
echo '========== 重启后校验 Nouveau =========='
if lsmod | grep -q nouveau; then
  echo 'ERROR: Nouveau 仍在加载，停止安装。'
  exit 30
fi
echo '========== 安装匹配当前内核的开发包 =========='
sudo yum install -y "kernel-devel-$(uname -r)" "kernel-headers-$(uname -r)"
echo '========== 检查 NVIDIA 驱动文件 =========='
test -s "$driver_file"
chmod +x "$driver_file"
echo '========== 安装 NVIDIA 驱动 =========='
sudo "./{GPU_DRIVER_FILE_NAME}" \\
  --kernel-source-path="/usr/src/kernels/$(uname -r)" \\
  --no-cc-version-check --no-opengl-files --disable-nouveau --dkms \\
  --no-questions --accept-license --ui=none
echo '========== 验证 NVIDIA 驱动 =========='
nvidia-smi
"""


def build_ubuntu_install_script() -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
driver_file='./{GPU_DRIVER_FILE_NAME}'
echo '========== 重启后校验 Nouveau =========='
if lsmod | grep -q nouveau; then
  echo 'ERROR: Nouveau 仍在加载，停止安装。'
  exit 30
fi
echo '========== 检查 NVIDIA 驱动文件 =========='
test -s "$driver_file"
chmod +x "$driver_file"
echo '========== 安装 NVIDIA 驱动 =========='
sudo "./{GPU_DRIVER_FILE_NAME}" \\
  --no-opengl-files --dkms --no-questions --accept-license \\
  --kernel-source-path=/lib/modules/$(uname -r)/build
echo '========== 验证 NVIDIA 驱动 =========='
nvidia-smi
"""


def _set_status(db, task: Task, status: str) -> None:
    task.status = status
    db.commit()
    try:
        ws_manager.broadcast_status_sync(task.task_id, status)
    except Exception:
        pass


def _log(db, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()
    try:
        ws_manager.broadcast_log_sync(task_id, level, message)
    except Exception:
        pass


def _update_params(db, task: Task, **values: str) -> None:
    params = dict(task.params or {})
    params.update(values)
    task.params = params
    db.commit()


def _connect(executor: SSHExecutor, server: Server) -> None:
    executor.connect(host=server.host, port=server.port, username=server.username,
                     key_path=server.key_path, password=server.password)


def _run_script(executor: SSHExecutor, remote_dir: str, script: str, timeout_seconds: int, log_line) -> int:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    command = f"printf %s {shell_quote(encoded)} | base64 -d | bash"
    return executor.exec_command_in_dir(command, remote_dir, timeout_seconds=timeout_seconds,
                                        on_stdout_line=log_line, on_stderr_line=log_line)


def _schedule_reboot(executor: SSHExecutor) -> None:
    # The background shell lets this SSH command return successfully before the
    # host goes away.  The following disconnect is therefore expected.
    executor.exec_simple("sudo bash -c '( sleep 3; systemctl reboot ) >/dev/null 2>&1 &'")


def _start_remote_install(executor: SSHExecutor, remote_dir: str, install_script: str | None = None) -> None:
    encoded = base64.b64encode((install_script or build_rocky9_install_script()).encode("utf-8")).decode("ascii")
    command = (
        f"cd {shell_quote(remote_dir)} && "
        f"printf %s {shell_quote(encoded)} | base64 -d > gpu-driver-install.sh && "
        "chmod 700 gpu-driver-install.sh && "
        "{ nohup bash -c 'bash ./gpu-driver-install.sh; rc=$?; printf \"%s\\n\" \"$rc\" > .gpu-driver.exit; exit \"$rc\"' "
        "</dev/null > gpu-driver-install.log 2>&1 & echo $! > .gpu-driver.pid; }"
    )
    executor.exec_simple(command)


def _read_boot_id(executor: SSHExecutor) -> str:
    return executor.exec_simple("cat /proc/sys/kernel/random/boot_id").strip()


def _wait_for_reboot(db, task: Task, server: Server, executor: SSHExecutor) -> bool:
    expected_boot_id = str((task.params or {}).get(GPU_DRIVER_BOOT_ID_KEY, ""))
    started = monotonic()
    while monotonic() - started < GPU_DRIVER_WAIT_REBOOT_SECONDS:
        db.refresh(task)
        if task.status in {"CANCELED", "CANCELING", "FAILED"}:
            return False
        try:
            executor.close()
            _connect(executor, server)
            current_boot_id = _read_boot_id(executor)
            if expected_boot_id and current_boot_id != expected_boot_id:
                _log(db, task.task_id, "SYSTEM", "server reboot confirmed; continuing NVIDIA driver installation")
                return True
            _log(db, task.task_id, "SYSTEM", "waiting for server reboot to complete")
        except SSHExecutorError as exc:
            _log(db, task.task_id, "SYSTEM", f"server is rebooting / SSH unavailable, retrying: {exc}")
        sleep(GPU_DRIVER_RECONNECT_INTERVAL_SECONDS)
    return False


def _monitor_remote_install(db, task: Task, executor: SSHExecutor) -> None:
    if not task.remote_work_dir:
        raise RuntimeError("remote work directory is missing")
    exit_file = f"{task.remote_work_dir.rstrip('/')}/.gpu-driver.exit"
    pid_file = f"{task.remote_work_dir.rstrip('/')}/.gpu-driver.pid"
    log_file = f"{task.remote_work_dir.rstrip('/')}/gpu-driver-install.log"
    while True:
        db.refresh(task)
        if task.status in {"CANCELED", "CANCELING"}:
            return
        code, output, _err = executor.exec_capture(
            f"if test -f {shell_quote(exit_file)}; then cat {shell_quote(exit_file)}; "
            f"elif test -f {shell_quote(pid_file)} && kill -0 \"$(cat {shell_quote(pid_file)})\" 2>/dev/null; then echo RUNNING; "
            "else echo MISSING; fi",
            timeout_seconds=15,
        )
        if code != 0:
            raise SSHExecutorError("cannot inspect remote NVIDIA installer state")
        state = output.strip()
        if state == "RUNNING":
            sleep(5)
            continue
        tail_code, tail, _ = executor.exec_capture(f"tail -80 {shell_quote(log_file)} 2>/dev/null || true", timeout_seconds=15)
        if tail:
            _log(db, task.task_id, "INFO" if state == "0" else "ERROR", tail[-4096:])
        task.end_time = datetime.utcnow()
        if state == "0":
            task.status = "SUCCESS"
            task.exit_code = 0
            task.error_message = None
            db.commit()
            try:
                ws_manager.broadcast_done_sync(task.task_id, "SUCCESS")
            except Exception:
                pass
            return
        task.status = "FAILED"
        task.exit_code = int(state) if state.isdigit() else None
        task.error_message = "NVIDIA driver installer ended without an exit code" if state == "MISSING" else f"NVIDIA driver installer exited with code {state}"
        db.commit()
        try:
            ws_manager.broadcast_done_sync(task.task_id, "FAILED")
        except Exception:
            pass
        return


def _schedule_retry(task_id: str) -> None:
    with _scheduled_retry_lock:
        if task_id in _scheduled_retry_ids:
            return
        _scheduled_retry_ids.add(task_id)

    def retry() -> None:
        sleep(60)
        with _scheduled_retry_lock:
            _scheduled_retry_ids.discard(task_id)
        run_rocky9_gpu_driver_task(task_id)

    threading.Thread(target=retry, daemon=True).start()


def run_rocky9_gpu_driver_task(task_id: str) -> None:
    db = SessionLocal()
    executor = SSHExecutor()
    task: Task | None = None
    phase = GPU_DRIVER_PHASE_INITIAL
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None or task.task_type != GPU_DRIVER_TASK_TYPE or task.status in {"SUCCESS", "FAILED", "CANCELED"}:
            return
        server = db.get(Server, task.server_id)
        if server is None:
            raise RuntimeError("server not found")
        params = task.params or {}
        driver_type = _optional_param_text(params.get("driver_type"))
        driver_id = _optional_param_text(params.get("driver_id"))
        upload_id = _optional_param_text(params.get("driver_upload_id"))
        force_install = bool(params.get("force_install_if_driver_exists", False))
        os_profile = str(params.get("os_profile", "")) or resolve_gpu_driver_os_profile(server.os_info)
        install_script = build_rocky9_install_script() if os_profile == "rocky9" else build_ubuntu_install_script()
        target_version: str | None = None
        if upload_id:
            uploaded_driver = resolve_uploaded_driver(upload_id)
        elif not driver_type or not driver_id:
            legacy_ref = LEGACY_GPU_DRIVER_LIBRARY_REFS.get(str(params.get("driver_source", "")))
            if legacy_ref is None:
                raise GpuDriverValidationError("GPU driver library entry is invalid")
            driver_type, driver_id = legacy_ref
            uploaded_driver = resolve_library_driver(driver_type, driver_id)
            target_version = driver_version_from_filename(uploaded_driver.name)
        else:
            uploaded_driver = resolve_library_driver(driver_type, driver_id)
            target_version = driver_version_from_filename(uploaded_driver.name)
        phase = str(params.get(GPU_DRIVER_PHASE_KEY, GPU_DRIVER_PHASE_INITIAL))

        _set_status(db, task, "CONNECTING")
        _connect(executor, server)
        remote_home = executor.get_remote_home()
        if not task.remote_work_dir:
            task.remote_work_dir = f"{remote_home.rstrip('/')}/hpcdeploy/tasks/gpu-driver/{task.task_id}"
            db.commit()
        executor.mkdir_p(task.remote_work_dir)

        if phase == GPU_DRIVER_PHASE_INITIAL:
            _set_status(db, task, "PREPARING")
            nvidia_smi_code, installed_versions, _nvidia_smi_error = executor.exec_capture(
                "nvidia-smi --query-gpu=driver_version --format=csv,noheader",
                timeout_seconds=20,
            )
            if should_skip_existing_driver(nvidia_smi_available=nvidia_smi_code == 0, force_install=force_install):
                task.start_time = datetime.utcnow()
                task.end_time = task.start_time
                task.exit_code = 0
                task.error_message = None
                task.status = "SUCCESS"
                db.commit()
                _log(db, task_id, "SYSTEM", "nvidia-smi is available; skipping NVIDIA driver installation")
                try:
                    ws_manager.broadcast_done_sync(task_id, "SUCCESS")
                except Exception:
                    pass
                return
            if nvidia_smi_code == 0 and force_install:
                _log(db, task_id, "SYSTEM", f"nvidia-smi is available; force installing selected driver (installed: {installed_versions.strip() or 'unknown'}, target: {target_version or 'custom'})")
            _log(db, task_id, "SYSTEM", "Rocky 9.4 NVIDIA driver: checking GPU, dependencies, system update and Nouveau")
            nouveau_code, _out, _err = executor.exec_capture("lsmod | grep -q nouveau", timeout_seconds=15)
            nouveau_loaded = nouveau_code == 0
            preparation_script = build_rocky9_pre_reboot_script(nouveau_loaded) if os_profile == "rocky9" else build_ubuntu_pre_reboot_script(nouveau_loaded)
            result = _run_script(executor, task.remote_work_dir, preparation_script, 7200,
                                 lambda line: _log(db, task_id, "INFO", line))
            if result != 0:
                raise RuntimeError(f"pre-reboot preparation exited with code {result}")
            kernel_reboot_required = False
            if os_profile == "rocky9":
                _kernel_code, kernel_check, _kernel_error = executor.exec_capture(
                    "if command -v grubby >/dev/null 2>&1 && [ \"$(basename \"$(grubby --default-kernel)\")\" != \"vmlinuz-$(uname -r)\" ]; then echo REBOOT_REQUIRED; fi",
                    timeout_seconds=15,
                )
                kernel_reboot_required = kernel_check.strip() == "REBOOT_REQUIRED"
            if should_reboot_for_gpu_driver(nouveau_loaded=nouveau_loaded, kernel_reboot_required=kernel_reboot_required):
                boot_id = _read_boot_id(executor)
                _update_params(db, task, **{GPU_DRIVER_PHASE_KEY: GPU_DRIVER_PHASE_WAITING_REBOOT, GPU_DRIVER_BOOT_ID_KEY: boot_id})
                _set_status(db, task, "WAITING_REBOOT")
                reason = "Nouveau is loaded" if nouveau_loaded else "a new default kernel is pending"
                _log(db, task_id, "SYSTEM", f"{reason}; preparation complete, rebooting server automatically")
                _schedule_reboot(executor)
                phase = GPU_DRIVER_PHASE_WAITING_REBOOT
            else:
                _log(db, task_id, "SYSTEM", "Nouveau is not loaded; skipping disable/reboot and continuing installation")
                if uploaded_driver is not None:
                    executor.upload_file(str(uploaded_driver), f"{task.remote_work_dir.rstrip('/')}/{GPU_DRIVER_FILE_NAME}")
                    _log(db, task_id, "SYSTEM", "local NVIDIA driver file uploaded")
                _start_remote_install(executor, task.remote_work_dir, install_script)
                _update_params(db, task, **{GPU_DRIVER_PHASE_KEY: GPU_DRIVER_PHASE_INSTALLING})
                task.start_time = task.start_time or datetime.utcnow()
                _set_status(db, task, "RUNNING")

        if phase == GPU_DRIVER_PHASE_WAITING_REBOOT:
            _set_status(db, task, "WAITING_REBOOT")
            if not _wait_for_reboot(db, task, server, executor):
                db.refresh(task)
                if task.status in {"CANCELED", "CANCELING"}:
                    return
                raise RuntimeError("server did not reconnect with a new boot_id within 30 minutes")
            db.refresh(task)
            if task.status in {"CANCELED", "CANCELING"}:
                return
            _set_status(db, task, "PREPARING")
            _log(db, task_id, "SYSTEM", "post-reboot verification passed; starting detached NVIDIA driver installer")
            if uploaded_driver is not None:
                executor.upload_file(str(uploaded_driver), f"{task.remote_work_dir.rstrip('/')}/{GPU_DRIVER_FILE_NAME}")
                _log(db, task_id, "SYSTEM", "local NVIDIA driver file uploaded")
            _start_remote_install(executor, task.remote_work_dir, install_script)
            _update_params(db, task, **{GPU_DRIVER_PHASE_KEY: GPU_DRIVER_PHASE_INSTALLING})
            task.start_time = task.start_time or datetime.utcnow()
            _set_status(db, task, "RUNNING")

        _monitor_remote_install(db, task, executor)
    except (GpuDriverValidationError, SSHExecutorError, RuntimeError) as exc:
        if isinstance(exc, SSHExecutorError) and task is not None and phase in {
            GPU_DRIVER_PHASE_WAITING_REBOOT,
            GPU_DRIVER_PHASE_INSTALLING,
        }:
            _log(db, task_id, "WARNING", f"GPU driver task connection unavailable; will retry: {exc}")
            _schedule_retry(task_id)
        elif task is not None:
            task.status = "FAILED"
            task.end_time = datetime.utcnow()
            task.error_message = str(exc)
            db.commit()
            _log(db, task_id, "ERROR", str(exc))
            try:
                ws_manager.broadcast_done_sync(task_id, "FAILED")
            except Exception:
                pass
    finally:
        executor.close()
        db.close()


def resume_gpu_driver_tasks_after_startup() -> int:
    db = SessionLocal()
    try:
        task_ids = [task_id for (task_id,) in db.query(Task.task_id).filter(
            Task.task_type == GPU_DRIVER_TASK_TYPE,
            Task.status.in_(("PENDING", "WAITING_REBOOT", "RUNNING")),
        ).all()]
    finally:
        db.close()
    for task_id in task_ids:
        threading.Thread(target=run_rocky9_gpu_driver_task, args=(task_id,), daemon=True).start()
    return len(task_ids)
