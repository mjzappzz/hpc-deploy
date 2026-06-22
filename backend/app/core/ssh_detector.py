from pathlib import Path
from socket import timeout as SocketTimeout

import paramiko


class ServerDetectError(Exception):
    pass


DETECT_COMMANDS: dict[str, str] = {
    "os_release": "cat /etc/os-release | head -20",
    "uname": "uname -a",
    "cpu_info": "lscpu | head -40",
    "memory_info": "free -h",
    "disk_info": "df -h",
    "gpu_info": "if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits; else echo 'NVIDIA GPU not detected or nvidia-smi not available'; fi",
}


def detect_server_info(
    *,
    host: str,
    port: int,
    username: str,
    key_path: str | None,
    password: str | None = None,
    timeout: int = 10,
) -> dict[str, str]:
    connect_kwargs: dict[str, object] = {}
    if password:
        connect_kwargs["password"] = password
    else:
        if not key_path:
            raise ServerDetectError("SSH key_path is not configured")
        key_file = Path(key_path).expanduser()
        if not key_file.is_file():
            raise ServerDetectError(f"SSH key file not found: {key_path}")
        connect_kwargs["key_filename"] = str(key_file)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
            **connect_kwargs,
        )
        return {name: _run_detect_command(client, command, timeout) for name, command in DETECT_COMMANDS.items()}
    except (SocketTimeout, TimeoutError) as exc:
        raise ServerDetectError(f"SSH connection timed out after {timeout}s") from exc
    except paramiko.AuthenticationException as exc:
        raise ServerDetectError("SSH authentication failed") from exc
    except paramiko.SSHException as exc:
        raise ServerDetectError(f"SSH connection failed: {exc}") from exc
    except OSError as exc:
        raise ServerDetectError(f"SSH network error: {exc}") from exc
    finally:
        client.close()


def summarize_detect_result(result: dict[str, str]) -> dict[str, str]:
    os_info = _extract_pretty_name(result.get("os_release", "")) or result.get("uname", "")
    cpu_info = _summarize_cpu_info(result.get("cpu_info", ""))
    memory_info = _summarize_memory_info(result.get("memory_info", ""))
    disk_info = _summarize_disk_info(result.get("disk_info", ""))
    gpu_info = _summarize_gpu_info(result.get("gpu_info", ""))
    return {
        "os_info": _compact(os_info),
        "cpu_info": _compact(cpu_info),
        "memory_info": _compact(memory_info),
        "disk_info": _compact(disk_info),
        "gpu_info": _compact(gpu_info),
        "network_info": "",
    }


def _run_detect_command(client: paramiko.SSHClient, command: str, timeout: int) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error = stderr.read().decode("utf-8", errors="replace").strip()
    if exit_code != 0:
        return error or output
    return output


def _extract_pretty_name(os_release: str) -> str:
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def _compact(value: str, limit: int = 500) -> str:
    compacted = " ".join(value.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3] + "..."


def _summarize_cpu_info(raw: str) -> str:
    model = ""
    cores = ""
    for line in raw.splitlines():
        if not model and line.startswith("Model name:"):
            model = line.split(":", 1)[1].strip()
        if not cores and line.startswith("CPU(s):"):
            cores = line.split(":", 1)[1].strip()
    if not model and not cores:
        return raw.strip() or "-"
    if model and cores:
        return f"{model} / {cores}C"
    return model or cores


def _summarize_memory_info(raw: str) -> str:
    for line in raw.splitlines():
        if line.strip().startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
    return raw.strip() or "-"


def _summarize_disk_info(raw: str) -> str:
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == "/":
            return f"/ {parts[1]} total / {parts[2]} used"
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 6:
            return f"{parts[-1]} {parts[1]} total / {parts[2]} used"
    return raw.strip() or "-"


def _summarize_gpu_info(raw: str) -> str:
    text = raw.strip()
    if not text:
        return "-"
    if "not detected" in text.lower() or "not available" in text.lower():
        return "无 NVIDIA GPU"

    counts: dict[str, int] = {}
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2 and parts[1]:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if not counts:
        return text
    return " / ".join(f"{name} x{count}" for name, count in counts.items())
