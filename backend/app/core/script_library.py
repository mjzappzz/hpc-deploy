from datetime import datetime
from pathlib import Path

from app.core.script_validator import BACKEND_ROOT, SCRIPTS_ROOT, ScriptValidationError


APPTAINER_ROOT = BACKEND_ROOT / "apptainer"
TEXT_FILE_SUFFIXES = {".sh", ".py", ".txt", ".md"}
BINARY_FILE_SUFFIXES = {".sif"}
ALLOWED_LIBRARY_SUFFIXES = TEXT_FILE_SUFFIXES | BINARY_FILE_SUFFIXES
UPLOAD_DIRECTORIES = {
    "mpi": SCRIPTS_ROOT / "mpi",
    "stress": SCRIPTS_ROOT / "stress",
    "apptainer": APPTAINER_ROOT,
}
ALLOWED_SUFFIXES_BY_CATEGORY = {
    "mpi": {".sh", ".py", ".txt", ".md"},
    "stress": {".sh", ".py", ".txt", ".md"},
    "apptainer": {".sif"},
}
DISPLAY_CATEGORY_LABELS = {
    "mpi": "服务器环境",
    "stress": "服务器压测",
    "apptainer": "Apptainer 容器",
}


def list_library_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for root in (SCRIPTS_ROOT, APPTAINER_ROOT):
        files.extend(_scan_root(root))
    return sorted(files, key=lambda item: (str(item["physical_category"]), str(item["name"])))


def normalize_library_path(file_path: str) -> str:
    return resolve_library_path(file_path).relative_to(BACKEND_ROOT).as_posix()


def get_library_file_record(file_path: str) -> dict[str, object]:
    normalized = normalize_library_path(file_path)
    return build_library_file_record(resolve_library_path(normalized))


def resolve_library_path(file_path: str) -> Path:
    raw_value = file_path.strip()
    if not raw_value:
        raise ScriptValidationError("file_path cannot be empty")

    raw_path = Path(raw_value)
    if raw_path.is_absolute():
        raise ScriptValidationError("absolute file_path is not allowed")
    if ".." in raw_path.parts:
        raise ScriptValidationError("../ path traversal is not allowed")

    candidate = (BACKEND_ROOT / raw_path).resolve(strict=False)
    if not _is_allowed_library_path(candidate):
        raise ScriptValidationError("file_path must stay under backend/scripts or backend/apptainer")
    if not candidate.is_file():
        raise ScriptValidationError(f"library file not found: {file_path}")
    if candidate.suffix.lower() not in ALLOWED_LIBRARY_SUFFIXES:
        raise ScriptValidationError("unsupported file suffix")
    return candidate


def save_library_file(category: str, filename: str, content: bytes) -> dict[str, object]:
    destination_dir = UPLOAD_DIRECTORIES.get(category)
    if destination_dir is None:
        raise ScriptValidationError(f"unsupported category: {category}")

    safe_name = Path(filename).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise ScriptValidationError("filename cannot be empty")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES_BY_CATEGORY[category]:
        raise ScriptValidationError("unsupported file suffix")

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / safe_name
    if destination.exists():
        raise ScriptValidationError(f"file already exists: {safe_name}")

    destination.write_bytes(content)
    return build_library_file_record(destination)


def delete_library_file(file_path: str) -> dict[str, object]:
    resolved = resolve_library_path(file_path)
    record = build_library_file_record(resolved)
    resolved.unlink()
    _cleanup_empty_parents(resolved.parent)
    return record


def read_library_preview(file_path: str, max_bytes: int = 200_000) -> dict[str, object]:
    resolved = resolve_library_path(file_path)
    record = build_library_file_record(resolved)
    if not bool(record["previewable"]):
        return {
            **record,
            "content": None,
            "truncated": False,
            "message": "binary file is not previewable",
        }

    raw = resolved.read_bytes()
    truncated = len(raw) > max_bytes
    content = raw[:max_bytes].decode("utf-8", errors="replace")
    return {
        **record,
        "content": content,
        "truncated": truncated,
        "message": None,
    }


def build_library_file_record(path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    physical_category = detect_library_category(resolved)
    relative = resolved.relative_to(BACKEND_ROOT).as_posix()
    relative_path = resolved.relative_to(
        APPTAINER_ROOT.resolve() if physical_category == "apptainer" else SCRIPTS_ROOT.resolve()
    ).as_posix()
    suffix = resolved.suffix.lower()
    stat = resolved.stat()
    try:
        updated_at = datetime.utcfromtimestamp(stat.st_mtime)
    except Exception:
        updated_at = None
    return {
        "path": relative,
        "resolved_path": str(resolved),
        "relative_path": relative_path,
        "name": resolved.name,
        "physical_category": physical_category,
        "display_category": DISPLAY_CATEGORY_LABELS[physical_category],
        "size": stat.st_size,
        "updated_at": updated_at,
        "executable": bool(stat.st_mode & 0o111),
        "is_text": suffix in TEXT_FILE_SUFFIXES,
        "previewable": suffix in TEXT_FILE_SUFFIXES,
    }


def detect_library_category(path: Path) -> str:
    resolved = path.resolve(strict=True)
    if _is_relative_to(resolved, APPTAINER_ROOT.resolve()):
        return "apptainer"
    try:
        relative = resolved.relative_to(SCRIPTS_ROOT.resolve())
    except ValueError:
        return "mpi"
    if relative.parts and relative.parts[0] == "stress":
        return "stress"
    return "mpi"


def _scan_root(root: Path) -> list[dict[str, object]]:
    resolved_root = root.resolve()
    if not resolved_root.exists():
        return []

    files: list[dict[str, object]] = []
    for path in sorted(resolved_root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(resolved_root).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        if path.suffix.lower() not in ALLOWED_LIBRARY_SUFFIXES:
            continue
        files.append(build_library_file_record(path))
    return files


def _is_allowed_library_path(path: Path) -> bool:
    resolved_scripts_root = SCRIPTS_ROOT.resolve()
    resolved_apptainer_root = APPTAINER_ROOT.resolve()
    return _is_relative_to(path, resolved_scripts_root) or _is_relative_to(path, resolved_apptainer_root)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cleanup_empty_parents(path: Path) -> None:
    for parent in (path, *path.parents):
        if parent in {SCRIPTS_ROOT.resolve(), APPTAINER_ROOT.resolve(), BACKEND_ROOT.resolve()}:
            return
        try:
            parent.rmdir()
        except OSError:
            return
