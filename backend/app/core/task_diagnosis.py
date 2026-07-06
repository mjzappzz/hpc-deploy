"""
Task failure diagnosis — rule-based, no external AI.

Categories are matched against log text by keyword patterns.
Returns structured diagnosis with title, causes, suggestions, evidence lines,
and enhanced fields: attribution, conclusion, risk_tips.

New metadata-based pre-check rules run before pattern matching:
  1. User cancel (exit_code == -15 / status == CANCELED)
  2. Artifact recovery failure (error message match)
  3. Report generated but task not finalized (artifacts exist + RUNNING status)
  4. Timeout without report (timeout pattern + no artifacts)
  5. Stress stuck at stress-ng stage (stage marker + duration exceeded)
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ──

_COLLECTED_FILE_EXTENSIONS = frozenset({".log", ".txt", ".csv", ".xlsx", ".json"})
_ACTIVE_STATUSES = frozenset({"PENDING", "CONNECTING", "PREPARING", "UPLOADING", "RUNNING"})

# ── Sensitive field filtering ────────────────────────────────────────

_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"private_key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"BEGIN\s+OPENSSH\s+PRIVATE\s+KEY"),
    re.compile(r"BEGIN\s+RSA\s+PRIVATE\s+KEY"),
    re.compile(r"BEGIN\s+EC\s+PRIVATE\s+KEY"),
]


def _filter_sensitive(text: str) -> str:
    """Replace sensitive content with ***."""
    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub("***", result)
    return result


# ── Category definitions ─────────────────────────────────────────────

CategoryDef = dict[str, Any]

CATEGORIES: list[CategoryDef] = [
    {
        "category": "command_timeout",
        "level": "error",
        "attribution": "timeout",
        "title": "任务执行超时",
        "conclusion": "任务运行时间超过平台允许的最大执行时间。",
        "summary": "任务运行时间超过平台允许的最大执行时间。",
        "possible_causes": [
            "压测时长较长，平台 timeout 缓冲不足",
            "脚本结束后生成报告或回收结果耗时过长",
            "远端进程没有按预期退出",
            "依赖安装或结果处理耗时过长",
        ],
        "suggestions": [
            "检查任务日志中压测是否已正常结束",
            "检查结果文件是否已经生成",
            "增大 stress 任务 timeout 缓冲",
            "对长时间压测任务预留更长收尾时间",
        ],
        "risk_tips": [
            "超时任务远端可能仍有进程在运行，建议登录服务器检查",
        ],
        "patterns": [
            "command timed out after",
            "TimeoutExpired",
            "timeout expired",
            "timed out after",
        ],
    },
    {
        "category": "ssh_auth_failed",
        "level": "error",
        "attribution": "environment",
        "title": "SSH 认证失败",
        "conclusion": "SSH 认证被拒绝，无法登录目标服务器。",
        "summary": "SSH 认证被拒绝，无法登录目标服务器。",
        "possible_causes": [
            "用户名不正确",
            "密码不正确",
            "私钥文件不正确或格式错误",
            "目标服务器 authorized_keys 未配置本机公钥",
        ],
        "suggestions": [
            "在服务器管理页检查用户名",
            "检查密码或私钥是否正确",
            "使用「部署公钥」功能将本机公钥添加到服务器",
            "确认 authorized_keys 文件权限为 600",
        ],
        "risk_tips": [
            "连续认证失败可能导致服务器 SSH 策略锁 IP，请注意频率",
        ],
        "patterns": [
            "Authentication failed",
            "Permission denied",
            "publickey",
            "invalid private key",
            "not a valid RSA private key file",
            "passphrase",
            "All configured authentication methods failed",
        ],
    },
    {
        "category": "ssh_connection_failed",
        "level": "error",
        "attribution": "environment",
        "title": "SSH 连接失败",
        "conclusion": "任务无法连接到目标服务器。",
        "summary": "任务无法连接到目标服务器。",
        "possible_causes": [
            "服务器 IP 或端口不正确",
            "服务器未开机或网络不可达",
            "SSH 服务未启动",
            "防火墙阻止了 22 端口",
        ],
        "suggestions": [
            "在服务器管理页执行「测试 SSH」",
            "确认主机地址和端口是否正确",
            "确认目标服务器 sshd 是否运行",
            "确认本机到目标服务器的网络连通性",
        ],
        "risk_tips": [],
        "patterns": [
            "timed out",
            "No route to host",
            "Network is unreachable",
            "Connection refused",
            "Unable to connect",
            "SSH connection timed out",
            "ssh_exchange_identification",
        ],
    },
    {
        "category": "disk_space_low",
        "level": "error",
        "attribution": "environment",
        "title": "磁盘空间不足",
        "conclusion": "远端服务器磁盘空间不足，无法继续执行。",
        "summary": "远端服务器磁盘空间不足，无法继续执行。",
        "possible_causes": [
            "远端服务器磁盘已满",
            "任务输出文件过大",
            "临时文件未及时清理",
        ],
        "suggestions": [
            "打开清理中心扫描远端临时目录",
            "清理 $HOME/hpcdeploy/tasks 目录",
            "检查目标盘剩余空间",
            "调整压测输出目录或减少输出量",
        ],
        "risk_tips": [
            "磁盘满可能导致远端服务异常，建议设置磁盘监控告警",
        ],
        "patterns": [
            "No space left on device",
            "disk quota exceeded",
            "write failed:",
            "insufficient space",
            "Disk quota exceeded",
        ],
    },
    {
        "category": "cuda_or_gpu_failed",
        "level": "error",
        "attribution": "environment",
        "title": "GPU/CUDA 环境异常",
        "conclusion": "GPU 或 NVIDIA 驱动环境不可用，导致 GPU 压测任务失败。",
        "summary": "GPU 或 NVIDIA 驱动环境不可用，导致 GPU 压测任务失败。",
        "possible_causes": [
            "目标服务器未安装 NVIDIA 驱动",
            "nvidia-smi 不存在或不可执行",
            "当前服务器没有 NVIDIA GPU",
            "驱动与 CUDA/NVML 库版本不匹配",
        ],
        "suggestions": [
            "在服务器管理页重新探测 GPU",
            "在远端执行 nvidia-smi 检查驱动",
            "确认服务器是否有 NVIDIA GPU",
            "如果没有 GPU，请不要执行 GPU 压测任务",
            "如驱动异常，请重新安装或修复 NVIDIA 驱动",
        ],
        "risk_tips": [
            "GPU 驱动升级后需要重启服务器才能生效",
        ],
        "patterns": [
            "nvidia-smi",
            "NVIDIA 驱动",
            "NVIDIA driver",
            "Failed to initialize NVML",
            "driver/library version mismatch",
            "no CUDA-capable device",
            "CUDA",
            "cuda",
            "GPU",
            "NVIDIA-SMI has failed",
        ],
    },
    {
        "category": "apptainer_upload_failed",
        "level": "error",
        "attribution": "environment",
        "title": "Apptainer 镜像分发失败",
        "conclusion": "Apptainer .sif 镜像文件上传或同步失败。",
        "summary": "Apptainer .sif 镜像文件上传或同步失败。",
        "possible_causes": [
            "远端 $HOME/hpcdeploy/apptainer 目录不可写",
            "同文件名已存在且未勾选覆盖",
            "本地 .sif 文件不存在",
            "网络连接不稳定导致 SFTP 传输失败",
        ],
        "suggestions": [
            "检查远端 $HOME/hpcdeploy/apptainer 目录是否可写",
            "如果同名的 .sif 文件已存在，勾选「覆盖同名文件」",
            "检查本地 .sif 文件是否存在",
            "检查网络连接",
        ],
        "risk_tips": [],
        "patterns": [
            "SFTP",
            "upload failed",
            "failed to upload",
            "remote file already exists",
            ".sif",
            "Failure",
        ],
    },
    {
        "category": "permission_denied",
        "level": "error",
        "attribution": "environment",
        "title": "权限不足",
        "conclusion": "远端用户没有执行操作的必要权限。",
        "summary": "远端用户没有执行操作的必要权限。",
        "possible_causes": [
            "远端用户对目标目录没有写权限",
            "文件权限设置不正确",
            "目标文件系统为只读",
        ],
        "suggestions": [
            "检查远端用户权限",
            "检查目录是否可写",
            "不建议直接使用 root 以外用户写系统目录",
        ],
        "risk_tips": [],
        "patterns": [
            "Operation not permitted",
            "chmod:",
            "cannot create directory",
            "read-only file system",
            "cannot remove",
        ],
    },
    {
        "category": "script_param_error",
        "level": "error",
        "attribution": "script",
        "title": "脚本参数错误",
        "conclusion": "传递给脚本的参数不正确或不完整。",
        "summary": "传递给脚本的参数不正确或不完整。",
        "possible_causes": [
            "参数格式不正确",
            "缺少必要参数",
            "参数值超出有效范围",
        ],
        "suggestions": [
            "检查任务参数是否正确",
            "使用任务模板重新创建任务",
            "确认压测时长、采样间隔、磁盘文件大小等参数格式",
        ],
        "risk_tips": [],
        "patterns": [
            "invalid option",
            "unrecognized option",
            "missing argument",
            "Usage:",
            "parameter",
            "params",
            "expected",
            "Illegal option",
        ],
    },
    {
        "category": "remote_path_failed",
        "level": "error",
        "attribution": "environment",
        "title": "远端路径错误",
        "conclusion": "远端工作目录或文件路径不存在或无法访问。",
        "summary": "远端工作目录或文件路径不存在或无法访问。",
        "possible_causes": [
            "远端工作目录不存在",
            "脚本或文件上传失败",
            "用户没有目录访问权限",
        ],
        "suggestions": [
            "检查远端工作目录配置",
            "确认脚本上传是否成功",
            "检查用户是否有目录权限",
        ],
        "risk_tips": [],
        "patterns": [
            "No such file or directory",
            "cannot access",
            "cd:",
            "mkdir: cannot create directory",
            "does not exist",
            "script file not found",
            "remote path not found",
            "workdir not found",
        ],
    },
    {
        "category": "command_exit_nonzero",
        "level": "error",
        "attribution": "script",
        "title": "命令非零退出",
        "conclusion": "远端命令执行完毕但返回了非零退出码。",
        "summary": "远端命令执行完毕但返回了非零退出码。",
        "possible_causes": [
            "脚本内部错误或异常",
            "输入数据或环境不符合预期",
            "依赖的程序或库缺失",
        ],
        "suggestions": [
            "查看上方关键日志片段定位具体错误",
            "检查脚本输出中的具体错误信息",
            "重新用较短时间或简化参数测试",
            "下载完整日志分析",
        ],
        "risk_tips": [],
        "patterns": [
            "exit code",
            "exited with code",
            "return code",
            "non-zero",
            "non-zero exit",
        ],
    },
    {
        "category": "unknown",
        "level": "warning",
        "attribution": "unknown",
        "title": "未知失败类型",
        "conclusion": "未能从日志中识别出具体的失败类型。",
        "summary": "未能从日志中识别出具体的失败类型。",
        "possible_causes": [
            "脚本内部逻辑错误",
            "输入数据或环境不符合预期",
            "依赖的程序或库缺失",
        ],
        "suggestions": [
            "下载完整日志查看详情",
            "查看实时日志观察执行过程",
            "检查服务器 SSH 连接、目录权限、脚本参数",
        ],
        "risk_tips": [],
        "patterns": [],
    },
]

# ── Metadata-based pre-check rules (checked before pattern matching) ──


def _precheck_user_canceled(
    task_status: str | None,
    error_message: str | None,
    exit_code: int | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 1: Task was canceled by user.

    Triggers when: exit_code == -15 (SIGTERM) or status == CANCELED
                   or error message contains "canceled by user".
    """
    if task_status == "CANCELED" or exit_code == -15:
        return {
            "level": "warning",
            "category": "user_canceled",
            "attribution": "user_cancel",
            "title": "任务被取消",
            "conclusion": "任务被用户取消或进程收到 SIGTERM 终止信号。",
            "summary": (
                "退出码为 -15（SIGTERM），任务状态为已取消。"
            ),
            "possible_causes": [
                "用户在任务执行过程中点击了取消按钮",
                "系统或管理员主动终止了任务",
            ],
            "suggestions": [
                "如需重新执行，请在任务执行页重新创建任务",
                "取消时远端文件默认保留，可在清理中心查看",
                "如确认不需要可手动清理远端目录",
            ],
            "risk_tips": [
                "取消时远端文件默认不删除，请确认不需要后手动清理",
            ],
        }

    if error_message and "canceled by user" in error_message.lower():
        return {
            "level": "warning",
            "category": "user_canceled",
            "attribution": "user_cancel",
            "title": "任务被取消",
            "conclusion": "任务被用户取消。",
            "summary": "错误信息显示任务被用户取消。",
            "possible_causes": [
                "用户在任务执行过程中点击了取消按钮",
            ],
            "suggestions": [
                "如需重新执行，请在任务执行页重新创建任务",
            ],
            "risk_tips": [
                "取消时远端文件默认不删除，请确认不需要后手动清理",
            ],
        }

    return None


def _precheck_batch_canceled(
    task_status: str | None,
    error_message: str | None,
    logs_joined: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 1a: Task was canceled by batch cancel."""
    if task_status != "CANCELED":
        return None

    text = "\n".join(filter(None, [error_message, logs_joined])).lower()
    if "canceled by batch cancel" not in text and "batch cancel requested" not in text:
        return None

    remote_unreachable = "remote unreachable" in text or "ssh unreachable" in text
    suggestions = [
        "如需确认远端进程，服务器恢复后检查进程",
        "如需清理结果，通过清理中心手动清理",
    ]
    risk_tips = ["批量取消不会删除远端目录。"]
    matched_patterns = ["canceled by batch cancel"]
    if remote_unreachable:
        risk_tips.append("服务器不可达时远端进程无法确认，请恢复后复核。")
        matched_patterns.append("remote unreachable")

    return {
        "level": "warning",
        "category": "batch_canceled",
        "attribution": "user_cancel",
        "title": "任务已被批量取消",
        "conclusion": "任务已被批量取消。",
        "summary": "平台已将该任务状态收口为已取消，已完成任务不受批量取消影响。",
        "possible_causes": [
            "用户在批次视图点击了取消批次",
        ],
        "suggestions": suggestions,
        "risk_tips": risk_tips,
        "matched_patterns": matched_patterns,
    }


def _precheck_canceled_remote_unreachable(
    task_status: str | None,
    error_message: str | None,
    logs_joined: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 1b: Task was canceled but remote server was unreachable."""
    if task_status != "CANCELED":
        return None

    text = "\n".join(filter(None, [error_message, logs_joined])).lower()
    markers = (
        "remote server unreachable",
        "ssh unreachable",
        "remote process not confirmed",
        "ssh connection failed",
        "ssh connection timed out",
    )
    if not any(marker in text for marker in markers):
        return None

    return {
        "level": "warning",
        "category": "user_canceled_remote_unreachable",
        "attribution": "platform",
        "title": "任务已取消，但远端不可达",
        "conclusion": "任务已取消，但取消时远端服务器不可达，无法确认远端进程是否已终止。",
        "summary": (
            "取消请求已经提交并在平台侧收口，但平台在尝试终止远端进程时遇到 SSH 不可达。"
            "远端进程是否仍在运行无法确认。"
        ),
        "possible_causes": [
            "目标服务器已宕机或网络不可达",
            "SSH 服务未响应，无法读取 PID 文件或发送 kill 信号",
            "取消请求发出时远端进程状态已无法确认",
        ],
        "suggestions": [
            "等待服务器恢复后检查远端进程是否仍在运行",
            "确认无用后，再通过清理中心手动清理远端目录",
            "检查任务日志中的 cancel requested 与 SSH unreachable 记录",
        ],
        "risk_tips": [
            "服务器恢复前，不要假设远端进程已经停止",
            "本次取消不会删除远端目录，需要人工复核后再清理",
        ],
        "matched_patterns": [
            "cancel requested by user",
            "SSH unreachable",
            "remote process not confirmed",
        ],
    }


def _precheck_artifact_recovery_failed(
    error_message: str | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 2: Remote report was generated but local artifact collection failed.

    Triggers when: error message contains "artifact recovery failed"
                   or "local artifact recovery failed".
    """
    if not error_message:
        return None

    text = error_message.lower()
    if "artifact recovery failed" in text or "local artifact recovery failed" in text:
        return {
            "level": "error",
            "category": "artifact_recovery_failed",
            "attribution": "artifact_failed",
            "title": "结果文件回收失败",
            "conclusion": "远端报告已生成但本地 artifact 回收失败。",
            "summary": (
                "远端服务器已生成报告文件，但平台在回收（下载）过程中失败，"
                "导致本地 artifacts 目录中缺少报告。"
            ),
            "possible_causes": [
                "SSH/SFTP 连接在下载过程中中断",
                "远端报告文件被意外删除或移动",
                "远端磁盘 I/O 错误导致文件不可读",
                "网络不稳定导致 SFTP 传输超时",
            ],
            "suggestions": [
                "在任务历史页手动点击「下载报告」重新回收",
                "登录服务器确认报告文件是否存在",
                "检查 SSH 连接状态和网络稳定性",
                "如一再失败可尝试在清理中心重新扫描",
            ],
            "risk_tips": [
                "远端报告文件仍保留在服务器上，不会丢失",
                "不要直接删除远端目录，先确认报告已下载",
            ],
        }

    return None


def _precheck_report_not_finalized(
    task_status: str | None,
    artifacts_present: bool,
    file_name: str | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 3: Reports exist on disk but task status was never finalized.

    Triggers when: task is in a non-terminal status (RUNNING etc.)
                   AND report files (*.xlsx, *.txt) exist in local artifacts dir.
    """
    if task_status in _ACTIVE_STATUSES and artifacts_present:
        return {
            "level": "warning",
            "category": "report_not_finalized",
            "attribution": "platform",
            "title": "报告已生成但任务状态未收尾",
            "conclusion": "报告已生成，但平台状态未收尾，属于平台 runner/recovery 问题。",
            "summary": (
                "本地 artifacts 目录已存在报告文件，但任务状态仍为 "
                f"{task_status}。这表明脚本已完成并生成了报告，"
                "但平台轮询/回收机制未正确更新任务状态。"
            ),
            "possible_causes": [
                "stress 异步 runner 在轮询周期内未及时检测到报告",
                "artifact collection 阶段 SSH/SFTP 异常中断",
                "多个 uvicorn worker 竞争状态更新导致状态不一致",
                "报告文件名不符合预期模式，未被收集逻辑匹配",
            ],
            "suggestions": [
                "刷新页面查看任务状态是否自动恢复",
                "确认报告文件已完整下载到本地",
                "如报告已完整，可尝试重新触发 artifact collection",
                "极端情况下可手动将任务标记为成功",
            ],
            "risk_tips": [
                "不要直接删除 RUNNING 状态任务，先确认报告已生成",
                "报告文件在本地 artifacts 目录可用，可先下载备份",
            ],
        }

    return None


def _precheck_timeout_no_report(
    logs_joined: str,
    artifacts_present: bool,
    task_status: str | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 4: Command timed out AND no report was generated.

    Triggers when: log contains timeout patterns AND artifacts dir has no reports.
    """
    if artifacts_present:
        return None

    timeout_patterns = [
        "command timed out after",
        "TimeoutExpired",
        "timeout expired",
        "timed out after",
    ]
    for pat in timeout_patterns:
        if pat.lower() in logs_joined.lower():
            return {
                "level": "error",
                "category": "timeout_no_report",
                "attribution": "timeout",
                "title": "任务超时且未生成报告",
                "conclusion": "任务超时且未生成有效报告，优先检查远端负载和脚本日志。",
                "summary": (
                    "任务执行超时，且本地 artifacts 目录未找到任何报告文件。"
                    "脚本可能未完成或未能生成预期产物。"
                ),
                "possible_causes": [
                    "stress-ng 在远端卡住未正常退出",
                    "脚本依赖安装（apt install、pip install）等待超时",
                    "远端系统负载过高，脚本执行缓慢",
                    "报告生成阶段脚本出错未生成文件",
                    "duration + grace 时间不足以让报告生成",
                ],
                "suggestions": [
                    "下载完整日志查看命令开始和中断位置",
                    "登录服务器检查 stress-ng 进程是否仍在运行",
                    "检查服务器当前 CPU/内存/磁盘负载",
                    "尝试使用更短的压测时间重新执行",
                    "检查是否需要在脚本中增加超时处理",
                ],
                "risk_tips": [
                    "超时任务远端可能有僵尸进程，建议登录服务器检查",
                    "长时间运行的 stress-ng 可能影响服务器稳定性",
                ],
            }

    return None


def _precheck_stress_preflight_failed(
    task_status: str | None,
    task_type: str | None,
    error_message: str | None,
    logs_joined: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    if task_type != "stress" or task_status != "FAILED":
        return None

    text = "\n".join(filter(None, [error_message, logs_joined])).lower()
    markers = (
        "stress failed before start",
        "gpu stress failed before start",
        "cpu/memory stress failed before start",
        "stress script exited before report generation",
        "nvidia-smi not found",
        "stress-ng not found",
        "python3-openpyxl not found",
        "no nvidia gpu detected",
        "unsupported os",
    )
    if not any(marker in text for marker in markers):
        return None

    return {
        "level": "error",
        "category": "stress_preflight_failed",
        "attribution": "environment",
        "title": "压测启动前置检查失败",
        "conclusion": error_message or "压测脚本未正常启动，平台已提前失败收口。",
        "summary": "平台检测到压测依赖、驱动或运行环境缺失，已终止等待并将任务标记为失败。",
        "possible_causes": [
            "GPU 压测缺少 NVIDIA 驱动、CUDA Toolkit、nvcc 或 gpu-burn",
            "CPU/内存或磁盘压测缺少 stress-ng",
            "缺少 python3-openpyxl，无法生成报告",
            "当前系统不在脚本支持范围内",
        ],
        "suggestions": [
            "按错误信息安装缺失依赖后重新执行",
            "GPU 压测先在远端验证 nvidia-smi、nvcc 和 gpu-burn",
            "CPU/内存压测先在远端验证 stress-ng 和 python3-openpyxl",
            "如为 stress-suite，后续压测会继续执行，请分别查看各子任务结果",
        ],
        "risk_tips": [
            "该任务未生成完整压测报告，不能作为硬件稳定性通过依据",
        ],
        "matched_patterns": [m for m in markers if m in text],
    }


def _precheck_stress_stuck(
    logs_joined: str,
    task_type: str | None,
    task_status: str | None,
    artifacts_present: bool,
    params: dict | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Rule 5: Stress script started but appears stuck before completion.

    Triggers when: log contains stress stage markers
                   AND (no artifacts OR status indicates active)
                   AND logs suggest stress-ng started but never finished.
    """
    if task_type != "stress":
        return None
    if task_status not in _ACTIVE_STATUSES:
        return None
    if not logs_joined:
        return None

    # Check for stress stage markers
    stage_markers = ["[STAGE] stress_start", "stress-ng"]
    has_stage_marker = any(marker.lower() in logs_joined.lower() for marker in stage_markers)
    if not has_stage_marker:
        return None

    # Check if duration+grace has likely passed (infer from params)
    duration_seconds = 0
    if params and isinstance(params.get("duration_seconds"), int):
        duration_seconds = params["duration_seconds"]
    if duration_seconds <= 0:
        return None

    return {
        "level": "warning",
        "category": "stress_stuck",
        "attribution": "environment",
        "title": "压测任务疑似卡住",
        "conclusion": "CPU/内存压测仍在 stress-ng 阶段，可能是脚本进程未按预期退出。",
        "summary": (
            f"日志显示压测（stress-ng）已启动（duration={duration_seconds}s），"
            "但任务状态仍未进入终态，且未检测到报告文件。"
            "脚本进程可能卡在 stress-ng 执行阶段或报告生成阶段未退出。"
        ),
        "possible_causes": [
            "stress-ng 压测进程未按预期退出（子进程挂起）",
            "报告生成脚本运行异常（等待资源、死锁）",
            "远端 shell 或进程组未正确清理",
            "SSH channel 断开后进程仍在远端运行",
        ],
        "suggestions": [
            "登录服务器检查 stress-ng 相关进程是否仍在运行",
            "检查远端 $HOME/hpcdeploy/tasks 下是否有卡住的进程文件",
            "如确认卡住可取消任务，使用 kill 清理远端进程",
            "重新创建任务，可考虑缩短单次压测时间",
        ],
        "risk_tips": [
            "卡住的 stress-ng 进程可能持续消耗 CPU/内存资源",
            "取消任务不会自动清理远端进程，需要手动确认",
        ],
    }


def _precheck_success(
    task_status: str | None,
    artifacts_present: bool,
    file_name: str | None,
    report_result: str | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Status check: Task completed successfully.

    Triggers when: task is in SUCCESS state.
    Returns different messages based on report content (PASS/FAIL).
    """
    if task_status != "SUCCESS":
        return None

    # If report says FAIL, indicate that
    conclusion = "任务已成功完成。"
    summary = "任务已完成，退出码为 0。"

    if report_result == "FAIL":
        conclusion = "平台任务已成功完成，但报告内压测结果为 FAIL。"
        summary += " 报告内容显示压测结果为 FAIL，请以报告内容为准判断硬件/压测是否通过。"
    elif report_result == "PASS":
        summary += " 报告内容显示压测结果为 PASS。"
    elif artifacts_present:
        summary += " 本地 artifacts 目录已保存报告文件，可查看报告确认压测结果。"
    else:
        summary += " 本地 artifacts 目录未找到报告文件（可能不需要生成报告）。"

    suggestions = [
        "可查看日志确认执行过程",
        "可下载报告 / 结果文件",
    ]
    if report_result == "FAIL":
        suggestions.append("报告内压测结果为 FAIL，请查看报告内失败指标")
    suggestions.append("如报告内压测结果为 PASS，压测验收通过")

    risk_tips = [
        "平台任务成功只表示脚本执行和报告回收完成",
        "压测验收 PASS/FAIL 以报告内容为准",
    ]

    return {
        "level": "info",
        "category": "completed",
        "attribution": "",
        "title": "任务执行成功",
        "conclusion": conclusion,
        "summary": summary,
        "possible_causes": [],
        "suggestions": suggestions,
        "risk_tips": risk_tips,
        "matched_patterns": [],
        "evidence": [],
    }


def _precheck_pending(
    task_status: str | None,
    artifacts_present: bool,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Status check: Task is still in pre-execution phase.

    Triggers when: status is PENDING, CONNECTING, PREPARING, or UPLOADING.
    """
    if task_status not in ("PENDING", "CONNECTING", "PREPARING", "UPLOADING"):
        return None

    status_labels = {
        "PENDING": "等待中",
        "CONNECTING": "连接中",
        "PREPARING": "准备中",
        "UPLOADING": "上传中",
    }
    label = status_labels.get(task_status, task_status or "未知")

    return {
        "level": "info",
        "category": "in_progress",
        "attribution": "",
        "title": "任务尚未开始执行",
        "conclusion": f"当前状态为「{label}」，任务尚未进入运行阶段。",
        "summary": (
            f"任务状态为 {task_status}（{label}），尚未开始实际执行。"
            "此时通常没有可用日志。"
        ),
        "possible_causes": [
            "批次任务等待前序任务完成后启动",
            "同服务器串行锁机制导致排队等待",
            "任务正在建立 SSH 连接或上传文件",
        ],
        "suggestions": [
            "稍后刷新查看任务状态是否推进",
            "如果长时间停留在 PENDING，检查批次调度状态",
            "如果停留在 CONNECTING/PREPARING，检查服务器 SSH 连通性",
        ],
        "risk_tips": [],
        "matched_patterns": [],
        "evidence": [],
    }


def _precheck_running(
    task_status: str | None,
    artifacts_present: bool,
    file_name: str | None,
    params: dict | None,
    logs: list[str] | None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Status check: Task is currently running.

    Triggers when: status is RUNNING.
    """
    if task_status != "RUNNING":
        return None

    parts = ["任务正在运行中。"]

    # Duration info
    duration_seconds = 0
    if params and isinstance(params.get("duration_seconds"), int):
        duration_seconds = params["duration_seconds"]
        if duration_seconds > 0:
            parts.append(f"设定压测时长 {duration_seconds}s。")

    # Stage info from logs
    stage_hint = ""
    if logs:
        for line in reversed(logs):
            low = line.lower()
            if "[stage]" in low:
                stage_hint = line.strip()
                break
    if stage_hint:
        parts.append(f"当前阶段：{stage_hint}")
    else:
        parts.append("尚未检测到阶段标记。")

    # Artifacts
    if artifacts_present:
        parts.append("注意：已检测到本地报告文件，但任务状态仍未收尾，可能是 runner/recovery 问题。")

    log_count = len(logs) if logs else 0

    return {
        "level": "info",
        "category": "running",
        "attribution": "",
        "title": "任务正在运行",
        "conclusion": "任务正在运行中。",
        "summary": " ".join(parts),
        "possible_causes": [],
        "suggestions": [
            "如果仍在正常时长内，继续等待任务完成",
            "已生成报告但状态未收尾时，可尝试刷新页面",
        ],
        "risk_tips": [
            "正在运行的任务不要重复创建或取消，除非确认需要",
        ],
        "matched_patterns": [],
        "evidence": [],
    }


_PRE_CHECKS = [
    # Priority 1-5: Error-specific pre-checks (metadata-based)
    ("batch_canceled", _precheck_batch_canceled),
    ("user_canceled_remote_unreachable", _precheck_canceled_remote_unreachable),
    ("user_canceled", _precheck_user_canceled),
    ("artifact_recovery_failed", _precheck_artifact_recovery_failed),
    ("report_not_finalized", _precheck_report_not_finalized),
    ("timeout_no_report", _precheck_timeout_no_report),
    ("stress_preflight_failed", _precheck_stress_preflight_failed),
    ("stress_stuck", _precheck_stress_stuck),
    # Priority 6-8: Status-based pre-checks
    ("success", _precheck_success),
    ("pending", _precheck_pending),
    ("running", _precheck_running),
]


# ── Evidence extraction ──────────────────────────────────────────────

_EVIDENCE_MAX_COUNT = 5
_EVIDENCE_MAX_LENGTH = 300


def _extract_evidence(
    log_lines: list[str],
    matched_patterns: list[str],
) -> list[str]:
    """Extract up to 5 evidence lines from logs.

    Priority: lines matching diagnosis patterns first,
    then last 10 lines of the log as fallback.
    """
    evidence: list[str] = []

    # Try to find lines matching the matched patterns
    for line in log_lines:
        if len(evidence) >= _EVIDENCE_MAX_COUNT:
            break
        for pattern in matched_patterns:
            if pattern.lower() in line.lower():
                truncated = line[:_EVIDENCE_MAX_LENGTH]
                evidence.append(truncated)
                break  # next line

    # If no evidence found, use last 10 lines
    if not evidence:
        for line in log_lines[-10:]:
            truncated = line[:_EVIDENCE_MAX_LENGTH]
            evidence.append(truncated)

    return evidence[:_EVIDENCE_MAX_COUNT]


# ── Result builder ───────────────────────────────────────────────────

def _build_result(
    cat: CategoryDef,
    matched: list[str],
    evidence: list[str],
    task_status: str | None,
) -> dict[str, Any]:
    """Build a diagnosis result dict from a matched category."""
    # Override level for non-FAILED tasks
    level = cat["level"]
    if task_status not in ("FAILED",):
        level = "warning" if task_status == "CANCELED" else "info"

    return {
        "level": level,
        "category": cat["category"],
        "attribution": cat.get("attribution", ""),
        "title": cat["title"],
        "conclusion": cat.get("conclusion", cat["summary"]),
        "summary": cat["summary"],
        "possible_causes": list(cat["possible_causes"]),
        "suggestions": list(cat["suggestions"]),
        "risk_tips": list(cat.get("risk_tips", [])),
        "matched_patterns": matched,
        "evidence": evidence,
    }


def _build_no_logs_result() -> dict[str, Any]:
    """Return result for tasks with no logs."""
    return {
        "level": "info",
        "category": "no_logs",
        "attribution": "",
        "title": "日志为空",
        "conclusion": "该任务没有日志记录。",
        "summary": "该任务没有日志记录。",
        "possible_causes": [
            "任务可能尚未开始执行",
            "日志记录被跳过或清理",
        ],
        "suggestions": [
            "确认任务是否已开始执行",
            "检查任务状态和服务器连接",
        ],
        "risk_tips": [],
        "matched_patterns": [],
        "evidence": [],
    }


# ── Main diagnosis function ──────────────────────────────────────────


def diagnose_task_failure(
    task_status: str | None,
    error_message: str | None,
    logs: list[str] | None,
    *,
    exit_code: int | None = None,
    task_type: str | None = None,
    server_name: str | None = None,
    file_name: str | None = None,
    params: dict | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    batch_id: str | None = None,
    artifacts_present: bool = False,
    report_result: str | None = None,
) -> dict[str, Any]:
    """Diagnose a task failure based on logs and rich task metadata.

    Args:
        task_status: Task status string (e.g. "FAILED", "SUCCESS").
        error_message: Task-level error message, if any.
        logs: List of log message strings from TaskLog rows.
        exit_code: Task process exit code.
        task_type: Task type ("stress", "script", "apptainer").
        server_name: Target server name for display.
        file_name: Script file name.
        params: Task params dict (duration_seconds, etc.).
        start_time: Task start time.
        end_time: Task end time.
        batch_id: Batch ID if task is part of a batch.
        artifacts_present: Whether report files exist in local artifacts dir.

    Returns:
        dict with keys: level, category, attribution, title, conclusion,
        summary, possible_causes, suggestions, risk_tips,
        matched_patterns, evidence.
    """
    if not logs:
        return _build_no_logs_result()

    # Build joined text for matching
    full_text = "\n".join(logs)
    full_text_filtered = _filter_sensitive(full_text)

    # Also filter individual lines for evidence
    filtered_logs = [_filter_sensitive(line) for line in logs]

    # ── Phase 1: Pre-check rules (metadata-based) ──
    # These run before pattern matching and can return early results.
    for _name, check_fn in _PRE_CHECKS:
        try:
            result = check_fn(
                logs_joined=full_text_filtered,
                task_status=task_status,
                error_message=error_message,
                exit_code=exit_code,
                task_type=task_type,
                artifacts_present=artifacts_present,
                params=params,
                file_name=file_name,
                logs=filtered_logs,
                report_result=report_result,
            )
            if result is not None:
                # Ensure all required fields are present (pre-checks may omit some)
                result.setdefault("matched_patterns", [])
                result.setdefault("evidence", [])
                if not result.get("evidence"):
                    result["evidence"] = _extract_evidence(
                        filtered_logs, result["matched_patterns"]
                    )
                return result
        except Exception:
            logger.warning("[diagnosis] pre-check %s failed", _name, exc_info=True)

    # ── Phase 2: Pattern matching (existing rules) ──
    for cat in CATEGORIES:
        if cat["category"] == "unknown":
            continue

        matched: list[str] = []
        for pattern in cat["patterns"]:
            if pattern.lower() in full_text_filtered.lower():
                matched.append(pattern)

        if matched:
            evidence = _extract_evidence(filtered_logs, matched)
            return _build_result(cat, matched, evidence, task_status)

    # ── No match fallback ──
    unknown_cat = CATEGORIES[-1]
    evidence = _extract_evidence(filtered_logs, [])
    return _build_result(unknown_cat, [], evidence, task_status)
