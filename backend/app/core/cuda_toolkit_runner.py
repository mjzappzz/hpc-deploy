"""OS-aware NVIDIA CUDA Toolkit installation tasks."""

from __future__ import annotations

import threading
import re
from datetime import datetime

from app.core.gpu_driver_runner import _connect, _log, _run_script, _set_status
from app.core.ssh_executor import SSHExecutor, SSHExecutorError
from app.core.ws_manager import ws_manager
from app.db.database import SessionLocal
from app.models.server import Server
from app.models.task import Task


CUDA_TOOLKIT_TASK_TYPE = "cuda_toolkit"
CUDA_TOOLKIT_FILE_NAME = "cuda-toolkit-install.sh"
CUDA_TOOLKIT_VERSIONS = ("11.8", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.8", "12.9", "13.0")


class CudaToolkitValidationError(ValueError):
    pass


def resolve_cuda_toolkit_os_profile(os_info: str | None) -> str:
    normalized = (os_info or "").lower()
    if "rocky" in normalized and re.search(r"(?:^|[^0-9])9(?:\.[0-9]+)?(?:[^0-9]|$)", normalized):
        return "rocky9"
    if "ubuntu" in normalized and "22.04" in normalized:
        return "ubuntu2204"
    if "ubuntu" in normalized and "24.04" in normalized:
        return "ubuntu2404"
    raise CudaToolkitValidationError(
        f"unsupported CUDA Toolkit operating system: {os_info or 'not detected'}"
    )


def validate_cuda_toolkit_version(version: str) -> str:
    if version not in CUDA_TOOLKIT_VERSIONS:
        raise CudaToolkitValidationError(f"unsupported CUDA Toolkit version: {version}")
    return version


def should_skip_existing_cuda_toolkit(*, nvcc_available: bool, force_install: bool) -> bool:
    return nvcc_available and not force_install


def cuda_toolkit_environment_commands(version: str) -> str:
    version = validate_cuda_toolkit_version(version)
    return "\n".join((
        f"export PATH=/usr/local/cuda-{version}/bin:$PATH",
        f"export LD_LIBRARY_PATH=/usr/local/cuda-{version}/lib64:$LD_LIBRARY_PATH",
        f"export CUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda-{version}",
        f"export CUDA_PATH=/usr/local/cuda-{version}",
    ))


def _log_cuda_toolkit_commands(db, task_id: str, version: str) -> None:
    _log(db, task_id, "SYSTEM", "如需仅当前终端临时加载，请执行：")
    _log(db, task_id, "SYSTEM", cuda_toolkit_environment_commands(version))
    _log(db, task_id, "SYSTEM", "如需验证环境，请执行：")
    _log(db, task_id, "SYSTEM", f"/usr/local/cuda-{version}/bin/nvcc --version")


def build_cuda_toolkit_install_script(os_profile: str, version: str, *, force_install: bool) -> str:
    version = validate_cuda_toolkit_version(version)
    package_suffix = version.replace(".", "-")
    package_name = f"cuda-toolkit-{package_suffix}"
    if os_profile == "rocky9":
        repository_steps = """sudo dnf -y install dnf-plugins-core ca-certificates curl
sudo dnf config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/cuda-rhel9.repo
sudo dnf clean all"""
        install_command = (
            f"sudo dnf -y reinstall {package_name}"
            if force_install
            else f"sudo dnf -y install {package_name}"
        )
    elif os_profile in {"ubuntu2204", "ubuntu2404"}:
        distro = os_profile
        repository_steps = f"""export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y ca-certificates curl
curl -fsSL -o /tmp/cuda-keyring.deb https://developer.download.nvidia.com/compute/cuda/repos/{distro}/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i /tmp/cuda-keyring.deb
rm -f /tmp/cuda-keyring.deb
sudo apt-get update"""
        install_command = (
            f"sudo apt-get -y install --reinstall {package_name}"
            if force_install
            else f"sudo apt-get -y install {package_name}"
        )
    else:
        raise CudaToolkitValidationError(f"unsupported CUDA Toolkit OS profile: {os_profile}")

    return f"""#!/usr/bin/env bash
set -euo pipefail
sudo -n true
echo '========== [1/4] 校验 NVIDIA 驱动 =========='
nvidia-smi
echo '========== [2/4] 配置 NVIDIA CUDA 软件源 =========='
{repository_steps}
echo '========== [3/4] 安装 CUDA Toolkit {version} =========='
{install_command}
echo '========== [4/4] 配置全局 CUDA 环境变量 =========='
sudo tee /etc/profile.d/cuda-{version}.sh >/dev/null <<'EOF'
export PATH=/usr/local/cuda-{version}/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-{version}/lib64:$LD_LIBRARY_PATH
export CUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda-{version}
export CUDA_PATH=/usr/local/cuda-{version}
EOF
sudo chmod 644 /etc/profile.d/cuda-{version}.sh
sudo ln -sfn /usr/local/cuda-{version} /usr/local/cuda
echo '========== 验证 CUDA Toolkit =========='
/usr/local/cuda-{version}/bin/nvcc --version
"""


def run_cuda_toolkit_task(task_id: str) -> None:
    db = SessionLocal()
    executor = SSHExecutor()
    task: Task | None = None
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None or task.task_type != CUDA_TOOLKIT_TASK_TYPE or task.status in {"SUCCESS", "FAILED", "CANCELED"}:
            return
        server = db.get(Server, task.server_id)
        if server is None:
            raise RuntimeError("server not found")
        params = task.params or {}
        version = validate_cuda_toolkit_version(str(params.get("cuda_version", "")))
        force_install = bool(params.get("force_install", False))
        os_profile = str(params.get("os_profile", "")) or resolve_cuda_toolkit_os_profile(server.os_info)

        _set_status(db, task, "CONNECTING")
        _connect(executor, server)
        nvidia_smi_code, _out, _err = executor.exec_capture("nvidia-smi", timeout_seconds=20)
        if nvidia_smi_code != 0:
            raise RuntimeError("NVIDIA driver is unavailable; install or repair the GPU driver first")

        nvcc_path = f"/usr/local/cuda-{version}/bin/nvcc"
        nvcc_code, _nvcc_out, _nvcc_err = executor.exec_capture(f"{nvcc_path} --version", timeout_seconds=20)
        if should_skip_existing_cuda_toolkit(nvcc_available=nvcc_code == 0, force_install=force_install):
            task.start_time = datetime.utcnow()
            task.end_time = task.start_time
            task.exit_code = 0
            task.error_message = None
            task.status = "SUCCESS"
            db.commit()
            _log(db, task_id, "SYSTEM", f"CUDA Toolkit {version} is already installed; skipping")
            _log_cuda_toolkit_commands(db, task_id, version)
            ws_manager.broadcast_done_sync(task_id, "SUCCESS")
            return

        remote_home = executor.get_remote_home()
        if not task.remote_work_dir:
            task.remote_work_dir = f"{remote_home.rstrip('/')}/hpcdeploy/tasks/cuda-toolkit/{task.task_id}"
            db.commit()
        executor.mkdir_p(task.remote_work_dir)
        _set_status(db, task, "PREPARING")
        _log(db, task_id, "SYSTEM", f"installing CUDA Toolkit {version} for {os_profile}")
        task.start_time = datetime.utcnow()
        _set_status(db, task, "RUNNING")
        exit_code = _run_script(
            executor,
            task.remote_work_dir,
            build_cuda_toolkit_install_script(os_profile, version, force_install=force_install),
            7200,
            lambda line: _log(db, task_id, "INFO", line),
        )
        if exit_code != 0:
            raise RuntimeError(f"CUDA Toolkit installer exited with code {exit_code}")
        verify_code, verify_output, _verify_err = executor.exec_capture(f"{nvcc_path} --version", timeout_seconds=20)
        if verify_code != 0:
            raise RuntimeError(f"CUDA Toolkit {version} verification failed")
        _log(db, task_id, "SYSTEM", verify_output.strip())
        _log_cuda_toolkit_commands(db, task_id, version)
        task.status = "SUCCESS"
        task.exit_code = 0
        task.end_time = datetime.utcnow()
        task.error_message = None
        db.commit()
        ws_manager.broadcast_done_sync(task_id, "SUCCESS")
    except (CudaToolkitValidationError, SSHExecutorError, RuntimeError) as exc:
        if task is not None:
            task.status = "FAILED"
            task.end_time = datetime.utcnow()
            task.error_message = str(exc)
            db.commit()
            _log(db, task_id, "ERROR", str(exc))
            ws_manager.broadcast_done_sync(task_id, "FAILED")
    finally:
        executor.close()
        db.close()


def resume_cuda_toolkit_tasks_after_startup() -> int:
    db = SessionLocal()
    try:
        task_ids = [task_id for (task_id,) in db.query(Task.task_id).filter(
            Task.task_type == CUDA_TOOLKIT_TASK_TYPE,
            Task.status == "PENDING",
        ).all()]
    finally:
        db.close()
    for task_id in task_ids:
        threading.Thread(target=run_cuda_toolkit_task, args=(task_id,), daemon=True).start()
    return len(task_ids)
