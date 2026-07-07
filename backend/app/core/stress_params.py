import re

from fastapi import HTTPException, status


STRESS_ALLOWED_INTERVALS: list[int] = [5, 10, 30, 60, 120]
STRESS_ALLOWED_DISK_FILE_SIZES: list[str] = ["1G", "10G", "50G", "100G"]
STRESS_ALLOWED_GPU_BACKENDS: list[str] = ["cuda"]
STRESS_ALL_PARAM_KEYS: set[str] = {
    "duration_seconds", "interval_seconds",
    "memory_percent", "workers",
    "disk_file_size", "disk_path", "disk_test_dir",
    "gpu_ids", "gpu_memory_percent", "gpu_backend",
}

_SAFE_DISK_DIR_PREFIXES: tuple[str, ...] = (
    "/data", "/mnt", "/scratch", "/public", "/home", "/root",
)

_SAFE_DISK_DIR_BLOCKLIST: tuple[str, ...] = (
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    "/boot", "/dev", "/proc", "/sys", "/run", "/var", "/tmp",
)

_DISK_DIR_DANGEROUS_CHARS: re.Pattern = re.compile(r"[;&|`$()\n\r\0 \*\?]")
_DISK_DIR_TRAVERSAL: str = ".."


def auto_calc_stress_interval(duration_seconds: int) -> int:
    if duration_seconds <= 600:
        return 10
    if duration_seconds <= 3600:
        return 30
    if duration_seconds <= 43200:
        return 60
    return 120


def validate_disk_test_dir(path: str) -> str:
    stripped = path.strip()

    if not stripped.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must be an absolute path",
        )

    if _DISK_DIR_TRAVERSAL in stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must not contain path traversal (..)",
        )

    if _DISK_DIR_DANGEROUS_CHARS.search(stripped):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir contains dangerous characters",
        )

    if stripped.endswith(("*", "?")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="disk_test_dir must not end with wildcard character",
        )

    if stripped in _SAFE_DISK_DIR_BLOCKLIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"disk_test_dir must not be a system directory ({stripped})",
        )

    if not stripped.startswith(_SAFE_DISK_DIR_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"disk_test_dir must start with one of: {', '.join(_SAFE_DISK_DIR_PREFIXES)}",
        )

    return stripped


def validate_stress_params(raw: dict[str, object], script_name: str) -> dict[str, object]:
    validated: dict[str, object] = {}

    dur = raw.get("duration_seconds")
    if not isinstance(dur, int) or dur < 10 or dur > 259200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_seconds must be an integer between 10 and 259200",
        )
    validated["duration_seconds"] = dur
    validated["interval_seconds"] = auto_calc_stress_interval(dur)

    if script_name == "cpu_mem_stress_report.sh":
        if "memory_percent" in raw:
            mp = raw["memory_percent"]
            if not isinstance(mp, int) or mp < 10 or mp > 95:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="memory_percent must be between 10 and 95")
            validated["memory_percent"] = mp
        if "workers" in raw:
            w = raw["workers"]
            if not isinstance(w, int) or w < 1 or w > 1024:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workers must be between 1 and 1024")
            validated["workers"] = w

    elif script_name == "disk_stress_report.sh":
        if "disk_file_size" in raw:
            dfs = raw["disk_file_size"]
            if dfs not in STRESS_ALLOWED_DISK_FILE_SIZES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"disk_file_size must be one of {STRESS_ALLOWED_DISK_FILE_SIZES}",
                )
            validated["disk_file_size"] = dfs
        if "disk_path" in raw:
            dp = raw["disk_path"]
            if not isinstance(dp, str) or not dp.startswith("~/") or ".." in dp:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disk_path must be under home directory (~/...)")
            validated["disk_path"] = dp
        if "disk_test_dir" in raw:
            dtd = raw["disk_test_dir"]
            if not isinstance(dtd, str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disk_test_dir must be a string")
            if dtd.strip():
                validated["disk_test_dir"] = validate_disk_test_dir(dtd)

    elif script_name == "gpu_stress_report.sh":
        if "gpu_ids" in raw:
            gpu_ids = raw["gpu_ids"]
            if not isinstance(gpu_ids, str) or not re.match(r'^(\d+(,\d+)*|all)$', gpu_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="gpu_ids must be 'all' or comma-separated numbers (e.g. '0,1')",
                )
            validated["gpu_ids"] = gpu_ids
        if "gpu_memory_percent" in raw:
            gmp = raw["gpu_memory_percent"]
            if not isinstance(gmp, int) or gmp < 10 or gmp > 95:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="gpu_memory_percent must be between 10 and 95")
            validated["gpu_memory_percent"] = gmp
        if "gpu_backend" in raw:
            if raw["gpu_backend"] not in STRESS_ALLOWED_GPU_BACKENDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"gpu_backend must be one of {STRESS_ALLOWED_GPU_BACKENDS}",
                )
            validated["gpu_backend"] = "cuda"

    for key in raw:
        if key not in STRESS_ALL_PARAM_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown param: {key}")

    return validated


def validate_stress_suite_params(raw: dict[str, object], *, has_disk: bool) -> dict[str, object]:
    for key in raw:
        if key not in STRESS_ALL_PARAM_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown param: {key}",
            )

    dur = raw.get("duration_seconds")
    if not isinstance(dur, int) or dur < 10 or dur > 259200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_seconds must be an integer between 10 and 259200",
        )

    suite_params: dict[str, object] = {
        "duration_seconds": dur,
        "interval_seconds": auto_calc_stress_interval(dur),
    }

    for key in raw:
        if key not in ("duration_seconds", "interval_seconds"):
            suite_params[key] = raw[key]

    dtd = suite_params.get("disk_test_dir")
    if dtd is not None and has_disk:
        if isinstance(dtd, str) and dtd.strip():
            suite_params["disk_test_dir"] = validate_disk_test_dir(dtd)

    return suite_params
