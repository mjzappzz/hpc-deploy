from pathlib import Path
from socket import timeout as SocketTimeout

import paramiko


class ServerDetectError(Exception):
    pass


DETECT_COMMANDS: dict[str, str] = {
    "hostname": "hostname",
    "uname": "uname -a",
    "os_release": "cat /etc/os-release 2>/dev/null || true",
    "cpu_model": "lscpu | awk -F: '/Model name/ {gsub(/^[ \\t]+/, \"\", $2); print $2; exit}'",
    "cpu_cores": "nproc 2>/dev/null || lscpu | awk -F: '/^CPU\\(s\\)/ {gsub(/^[ \\t]+/, \"\", $2); print $2; exit}'",
    "memory_total": "free -h | awk '/^Mem:/ {print $2}'",
    "disk_summary": "df -h --total 2>/dev/null | tail -n 1 || df -h | tail -n +2",
    "gpu_info": "if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; else echo 'NVIDIA GPU not detected'; fi",
    "network_info": "hostname -I 2>/dev/null || ip -brief addr show scope global 2>/dev/null || true",
}


def detect_server_info(
    *,
    host: str,
    port: int,
    username: str,
    key_path: str | None,
    timeout: int = 10,
) -> dict[str, str]:
    if not key_path:
        raise ServerDetectError("SSH key_path is not configured")

    key_file = Path(key_path).expanduser()
    if not key_file.is_file():
        raise ServerDetectError(f"SSH key file not found: {key_path}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=str(key_file),
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
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
    cpu_model = result.get("cpu_model", "").strip() or "unknown CPU"
    cpu_cores = result.get("cpu_cores", "").strip() or "unknown cores"
    return {
        "os_info": _compact(os_info),
        "cpu_info": _compact(f"{cpu_model} / {cpu_cores} cores"),
        "memory_info": _compact(result.get("memory_total", "")),
        "disk_info": _compact(result.get("disk_summary", "")),
        "gpu_info": _compact(result.get("gpu_info", "")),
        "network_info": _compact(result.get("network_info", "")),
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
