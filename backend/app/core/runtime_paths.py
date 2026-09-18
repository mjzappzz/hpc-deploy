from dataclasses import dataclass
from pathlib import Path

from app.core.config import BACKEND_ROOT


@dataclass(frozen=True)
class RuntimePathSpec:
    key: str
    label: str
    path: Path | str
    kind: str
    description: str
    attention: bool = False


LOCAL_RUNTIME_PATHS = (
    RuntimePathSpec("database", "SQLite 主数据库", BACKEND_ROOT / "data" / "hpc_control_panel.db", "file", "服务器、任务、日志、系统设置、审计和报告摘要缓存都在这里。", True),
    RuntimePathSpec("ssh_keys", "SSH 密钥目录", BACKEND_ROOT / "keys", "directory", "用户放置或系统生成的 SSH 私钥/公钥。密钥不进入 Git。", True),
    RuntimePathSpec("mpi_scripts", "服务器环境脚本库", BACKEND_ROOT / "scripts" / "mpi", "directory", "服务器环境、安装、运维配置脚本，任务执行时按选择上传到远端。"),
    RuntimePathSpec("stress_scripts", "Linux 服务器压测脚本库", BACKEND_ROOT / "scripts" / "stress", "directory", "GPU、CPU/内存、磁盘 Linux 服务器压测脚本，执行任务时按选择上传到远端。"),
    RuntimePathSpec("gpu_driver_library", "Linux NVIDIA 驱动库", BACKEND_ROOT / "data" / "gpu_driver_library", "directory", "脚本知识库上传的 GeForce、Data Center（RTX Enterprise）NVIDIA .run 驱动文件。", True),
    RuntimePathSpec("gpu_driver_uploads", "临时自定义驱动", BACKEND_ROOT / "data" / "gpu_driver_uploads", "directory", "任务执行页临时上传的 NVIDIA .run 驱动；默认保留 7 天，任务执行中不会清理。", True),
    RuntimePathSpec("artifacts", "远端回收结果", BACKEND_ROOT / "data" / "artifacts", "directory", "远端拉回来的报告、日志、CSV、XLSX、JSON 等任务结果。", True),
    RuntimePathSpec("sqlite_backups", "数据库备份目录", BACKEND_ROOT / "data" / "backups", "directory", "scripts/backup_sqlite.sh 生成的 SQLite 备份文件。", True),
    RuntimePathSpec("apptainer", "Apptainer 镜像目录", BACKEND_ROOT / "apptainer", "directory", ".sif 镜像存放目录，镜像不进入 Git。", True),
)

REMOTE_RUNTIME_PATHS = (
    RuntimePathSpec("remote_tasks", "远端任务工作目录", "$HOME/hpcdeploy/tasks/<task_type>/<task_id>/", "remote", "每台目标服务器执行任务时生成，包含 task.log、.hpcdeploy.pid、报告和临时文件；覆盖 GPU 驱动与 CUDA 安装任务。", True),
    RuntimePathSpec("remote_apptainer", "远端 Apptainer 目录", "$HOME/hpcdeploy/apptainer/", "remote", "每台目标服务器上的 .sif 镜像分发目录。", True),
)
