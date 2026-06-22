import logging
import re
from pathlib import Path
from socket import timeout as SocketTimeout
from time import monotonic as time_monotonic

import paramiko

logger = logging.getLogger(__name__)


class ServerDetectError(Exception):
    pass


# Shared timeout for health/detect probes (both single-server and bulk).
# 3s is sufficient to determine SSH connectivity; a longer timeout would
# make bulk probe-all unacceptably slow when servers are offline.
DEFAULT_DETECT_TIMEOUT = 3


# Consolidated bash probe script — runs as a single exec_command.
# Sections are delimited by unique markers so the output can be split server-side.
# Using `|| df -h` fallback for systems where df --local is unsupported (e.g. BusyBox).
# nvidia-smi guarded with `timeout 3s` so a hung GPU driver never stalls the probe.
CONSOLIDATED_PROBE_SCRIPT = r"""
echo '__HPROBE_SECT_B__os'
cat /etc/os-release 2>/dev/null | head -20
echo '__HPROBE_SECT_E__'
echo '__HPROBE_SECT_B__uname'
uname -a 2>/dev/null
echo '__HPROBE_SECT_E__'
echo '__HPROBE_SECT_B__cpu'
lscpu 2>/dev/null | head -40
echo '__HPROBE_SECT_E__'
echo '__HPROBE_SECT_B__memory'
free -h 2>/dev/null
echo '__HPROBE_SECT_E__'
echo '__HPROBE_SECT_B__disk'
(df -h --local 2>/dev/null || df -h 2>/dev/null)
echo '__HPROBE_SECT_E__'
echo '__HPROBE_SECT_B__gpu'
if command -v nvidia-smi >/dev/null 2>&1; then
  timeout 3 nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo 'NVIDIA GPU query timed out or failed'
else
  echo 'NVIDIA GPU not detected or nvidia-smi not available'
fi
echo '__HPROBE_SECT_E__'
"""

# Regex to extract sections from the consolidated script output.
# Matches: __HPROBE_SECT_B__<name>\n<content>\n__HPROBE_SECT_E__
_SECTION_RE = re.compile(
    r"__HPROBE_SECT_B__(?P<name>\w+)\n(?P<content>.*?)\n__HPROBE_SECT_E__",
    re.DOTALL,
)


def detect_server_info(
    *,
    host: str,
    port: int,
    username: str,
    key_path: str | None,
    password: str | None = None,
    timeout: int = DEFAULT_DETECT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, float]]:
    """
    Probe a server and return (raw_data, timings).

    raw_data keys: os_release, uname, cpu_info, memory_info, disk_info, gpu_info
    timings keys:  connect, os, uname, cpu, memory, disk, gpu, total
    """
    timings: dict[str, float] = {}
    total_start = time_monotonic()

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
        connect_start = time_monotonic()
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
        timings["connect"] = round(time_monotonic() - connect_start, 3)
        logger.info(
            "[probe-timing] %s:%d connect elapsed=%.3fs",
            host, port, timings["connect"],
        )

        # Execute the consolidated probe script
        exec_start = time_monotonic()
        _stdin, stdout, stderr = client.exec_command(
            CONSOLIDATED_PROBE_SCRIPT, timeout=timeout,
        )
        exit_code = stdout.channel.recv_exit_status()
        raw_output = stdout.read().decode("utf-8", errors="replace").strip()
        err_output = stderr.read().decode("utf-8", errors="replace").strip()

        exec_elapsed = round(time_monotonic() - exec_start, 3)
        logger.info(
            "[probe-timing] %s:%d consolidated_script elapsed=%.3fs exit_code=%d",
            host, port, exec_elapsed, exit_code,
        )

        # Parse sections
        sections: dict[str, str] = {}
        for match in _SECTION_RE.finditer(raw_output):
            name = match.group("name")
            content = match.group("content").strip()
            sections[name] = content

        # Build result dict — missing sections get empty string
        raw_data: dict[str, str] = {
            "os_release": sections.get("os", ""),
            "uname": sections.get("uname", ""),
            "cpu_info": sections.get("cpu", ""),
            "memory_info": sections.get("memory", ""),
            "disk_info": sections.get("disk", ""),
            "gpu_info": sections.get("gpu", ""),
        }

        # Log per-section timing by tracking elapsed for each
        # We can't get per-section wall time from the client side,
        # but the script executes sections sequentially so the
        # exit tells us the script completed. Log output size as a heuristic.
        for name in ("os", "uname", "cpu", "memory", "disk", "gpu"):
            content = sections.get(name, "")
            size = len(content)
            marker = "OK" if content else "EMPTY"
            logger.info(
                "[probe-timing] %s:%d section=%s size=%d %s",
                host, port, name, size, marker,
            )

        timings["total"] = round(time_monotonic() - total_start, 3)
        logger.info(
            "[probe-timing] %s:%d total elapsed=%.3fs",
            host, port, timings["total"],
        )

        return raw_data, timings

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
