"""
Task failure diagnosis — rule-based, no external AI.

Categories are matched against log text by keyword patterns.
Returns structured diagnosis with title, causes, suggestions, and evidence lines.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

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
        "category": "ssh_auth_failed",
        "level": "error",
        "title": "SSH 认证失败",
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
        "title": "SSH 连接失败",
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
        "title": "磁盘空间不足",
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
        "title": "GPU/CUDA 环境异常",
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
        "title": "Apptainer 镜像分发失败",
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
        "title": "权限不足",
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
        "title": "脚本参数错误",
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
        "title": "远端路径错误",
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
        "title": "命令非零退出",
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
        "title": "未知失败类型",
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
        "patterns": [],
    },
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


# ── Main diagnosis function ──────────────────────────────────────────


def diagnose_task_failure(
    task_status: str | None,
    error_message: str | None,
    logs: list[str] | None,
) -> dict[str, Any]:
    """Diagnose a task failure based on logs and task metadata.

    Args:
        task_status: Task status string (e.g. "FAILED", "SUCCESS").
        error_message: Task-level error message, if any.
        logs: List of log message strings from TaskLog rows.

    Returns:
        dict with keys: level, category, title, summary,
        possible_causes, suggestions, matched_patterns, evidence.
    """
    if not logs:
        return {
            "level": "info",
            "category": "no_logs",
            "title": "日志为空",
            "summary": "该任务没有日志记录。",
            "possible_causes": [
                "任务可能尚未开始执行",
                "日志记录被跳过或清理",
            ],
            "suggestions": [
                "确认任务是否已开始执行",
                "检查任务状态和服务器连接",
            ],
            "matched_patterns": [],
            "evidence": [],
        }

    # Build full text for matching
    full_text = "\n".join(logs)
    full_text_filtered = _filter_sensitive(full_text)

    # Also filter individual lines for evidence
    filtered_logs = [_filter_sensitive(line) for line in logs]

    # Determine logging level based on task status
    base_level = "info"
    if task_status == "FAILED":
        base_level = "error"
    elif task_status == "CANCELED":
        base_level = "warning"

    # Try to match each category in order (unknown has no patterns, it's last)
    for cat in CATEGORIES:
        if cat["category"] == "unknown":
            continue

        matched: list[str] = []
        for pattern in cat["patterns"]:
            if pattern.lower() in full_text_filtered.lower():
                matched.append(pattern)

        if matched:
            evidence = _extract_evidence(filtered_logs, matched)
            result: dict[str, Any] = {
                "level": cat["level"],
                "category": cat["category"],
                "title": cat["title"],
                "summary": cat["summary"],
                "possible_causes": list(cat["possible_causes"]),
                "suggestions": list(cat["suggestions"]),
                "matched_patterns": matched,
                "evidence": evidence,
            }
            # Override level for non-FAILED tasks
            if task_status not in ("FAILED",):
                result["level"] = "warning" if task_status == "CANCELED" else "info"
            return result

    # No match — return unknown
    unknown_cat = CATEGORIES[-1]  # unknown
    evidence = _extract_evidence(filtered_logs, [])
    result = {
        "level": unknown_cat["level"],
        "category": unknown_cat["category"],
        "title": unknown_cat["title"],
        "summary": unknown_cat["summary"],
        "possible_causes": list(unknown_cat["possible_causes"]),
        "suggestions": list(unknown_cat["suggestions"]),
        "matched_patterns": [],
        "evidence": evidence,
    }
    if task_status not in ("FAILED",):
        result["level"] = "warning" if task_status == "CANCELED" else "info"
    return result
