from pathlib import Path
from typing import Any


class ScriptValidationError(Exception):
    pass


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"


def normalize_script_path(file_path: str) -> str:
    resolved = resolve_script_path(file_path)
    return resolved.relative_to(SCRIPTS_ROOT.resolve()).as_posix()


def resolve_script_path(file_path: str) -> Path:
    raw_value = file_path.strip()
    if not raw_value:
        raise ScriptValidationError("file_path cannot be empty")

    raw_path = Path(raw_value)
    if raw_path.is_absolute():
        raise ScriptValidationError("absolute file_path is not allowed")

    if ".." in raw_path.parts:
        raise ScriptValidationError("../ path traversal is not allowed")

    if raw_path.parts and raw_path.parts[0] in {"backend", "scripts"}:
        raise ScriptValidationError("file_path must be relative to backend/scripts, for example stress/cpu_mem_stress_report.sh")

    candidate = SCRIPTS_ROOT / raw_path

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(SCRIPTS_ROOT.resolve())
    except ValueError as exc:
        raise ScriptValidationError("file_path must stay under backend/scripts") from exc

    if not resolved.is_file():
        raise ScriptValidationError(f"script file not found: {file_path}")

    if resolved.suffix not in {".sh", ".py"}:
        raise ScriptValidationError("script file must use .sh or .py suffix")

    return resolved


def validate_params_schema(params_schema: dict[str, Any] | None) -> dict[str, Any]:
    return params_schema or {}
