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
# --- Step 1: lspci hardware detection ---
if command -v lspci >/dev/null 2>&1; then
  lspci | grep -i nvidia || echo '__LSPCI_NO_NVIDIA__'
else
  echo '__LSPCI_NOT_AVAILABLE__'
fi
echo '---GPU-SPLIT---'
# --- Step 2: nvidia-smi driver detection ---
if command -v nvidia-smi >/dev/null 2>&1; then
  timeout 3 nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo '__NVIDIA_SMI_FAILED__'
else
  echo '__NVIDIA_SMI_NOT_FOUND__'
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
    gpu_info, gpu_status = _summarize_gpu_info(result.get("gpu_info", ""))
    return {
        "os_info": _compact(os_info),
        "cpu_info": _compact(cpu_info),
        "memory_info": _compact(memory_info),
        "disk_info": _compact(disk_info),
        "gpu_info": _compact(gpu_info),
        "gpu_status": gpu_status,
        "network_info": "",
    }


def _extract_pretty_name(os_release: str) -> str:
    fields: dict[str, str] = {}
    for line in os_release.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip().strip('"')
    if fields.get("PRETTY_NAME"):
        return fields["PRETTY_NAME"]
    if fields.get("NAME") and fields.get("VERSION_ID"):
        return f"{fields['NAME']} {fields['VERSION_ID']}"
    if fields.get("NAME") and fields.get("VERSION"):
        return f"{fields['NAME']} {fields['VERSION']}"
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


def _summarize_gpu_info(raw: str) -> tuple[str, str]:
    """Parse raw GPU probe data and return (gpu_info, gpu_status).

    gpu_status is one of:
      "none"          — no NVIDIA PCI device found via lspci
      "hardware_only" — NVIDIA PCI device found but nvidia-smi unavailable
      "driver_ok"     — nvidia-smi returned valid GPU data
      "unknown"       — cannot determine (lspci unavailable, no data)
    """
    text = raw.strip()
    if not text:
        return "-", "unknown"

    # Split into lspci (hardware) and nvidia-smi (driver) sections
    parts = text.split("---GPU-SPLIT---")
    lspci_text = parts[0].strip() if len(parts) >= 1 else ""
    smi_text = parts[1].strip() if len(parts) >= 2 else ""

    # ── Determine driver availability ──
    smi_ok = bool(
        smi_text
        and "__NVIDIA_SMI_NOT_FOUND__" not in smi_text
        and "__NVIDIA_SMI_FAILED__" not in smi_text
    )

    if smi_ok:
        # Driver is working — parse GPU model names from nvidia-smi CSV
        counts: dict[str, int] = {}
        for line in smi_text.splitlines():
            row = [p.strip() for p in line.split(",")]
            if len(row) >= 2 and row[1]:
                counts[row[1]] = counts.get(row[1], 0) + 1
        if counts:
            return " / ".join(f"{name} x{c}" for name, c in counts.items()), "driver_ok"
        return smi_text[:200], "driver_ok"

    # ── nvidia-smi unavailable — check lspci for hardware ──
    lspci_has_hardware = bool(
        lspci_text
        and "__LSPCI_NO_NVIDIA__" not in lspci_text
        and "__LSPCI_NOT_AVAILABLE__" not in lspci_text
    )

    if lspci_has_hardware:
        model = _extract_lspci_model(lspci_text)
        info = "检测到 NVIDIA GPU，驱动不可用或 nvidia-smi 不存在"
        return info, "hardware_only"

    if "__LSPCI_NOT_AVAILABLE__" in lspci_text:
        return "-", "unknown"

    return "无 NVIDIA GPU", "none"


def _extract_lspci_model(lspci_text: str) -> str:
    """Try to extract a human-readable NVIDIA GPU model name from lspci output."""
    for line in lspci_text.splitlines():
        line = line.strip()
        if "nvidia" not in line.lower():
            continue
        # Try bracketed model name: "... [GeForce RTX 3080] ..."
        m = re.search(r"\[([^\]]*)\]", line)
        if m:
            candidate = m.group(1).strip()
            # Skip generic description words
            if candidate and not candidate.startswith("rev") and not candidate.startswith("NVIDIA"):
                return candidate
        # Fallback: extract text after last colon
        parts = line.split(":")
        if len(parts) >= 2:
            desc = parts[-1].strip()
            # Remove common prefix noise
            desc = re.sub(r"^.*?NVIDIA\s+Corporation\s+", "", desc)
            # Take the first meaningful chunk
            desc = re.sub(r"\s+\(.*$", "", desc)
            if desc and "nvidia" not in desc.lower():
                return desc
    return ""
