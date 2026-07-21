import hashlib
import re
from datetime import datetime
from pathlib import Path

from app.core.script_validator import BACKEND_ROOT, SCRIPTS_ROOT, ScriptValidationError


APPTAINER_ROOT = BACKEND_ROOT / "apptainer"
WINDOWS_SCRIPTS_ROOT = SCRIPTS_ROOT / "windows"
TEXT_FILE_SUFFIXES = {".sh", ".py", ".txt", ".md", ".ps1", ".bat", ".cmd"}
BINARY_FILE_SUFFIXES = {".sif"}
ALLOWED_LIBRARY_SUFFIXES = TEXT_FILE_SUFFIXES | BINARY_FILE_SUFFIXES
UPLOAD_DIRECTORIES = {
    "mpi": SCRIPTS_ROOT / "mpi",
    "stress": SCRIPTS_ROOT / "stress",
    "windows": WINDOWS_SCRIPTS_ROOT,
    "apptainer": APPTAINER_ROOT,
}
ALLOWED_SUFFIXES_BY_CATEGORY = {
    "mpi": {".sh", ".py", ".txt", ".md"},
    "stress": {".sh", ".py", ".txt", ".md"},
    "windows": {".ps1", ".bat", ".cmd"},
    "apptainer": {".sif"},
}
DISPLAY_CATEGORY_LABELS = {
    "mpi": "服务器环境",
    "stress": "服务器压测",
    "windows": "Windows 压测",
    "apptainer": "Apptainer 容器",
}
MAX_WINDOWS_SCRIPT_BYTES = 2 * 1024 * 1024
VERSION_VALUE = r"(?P<version>\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9._-]+)?)"
SCRIPT_VERSION_PATTERN = re.compile(
    rf"^\s*(?:#|REM\s+)?\s*(?:script\s*version|version)\s*[:=]\s*['\"]?v?{VERSION_VALUE}",
    re.IGNORECASE | re.MULTILINE,
)
SCRIPT_HEADER_VERSION_PATTERN = re.compile(
    rf"\b(?:script|report|stress)\b[^\r\n]{{0,160}}?\bv?{VERSION_VALUE}\b",
    re.IGNORECASE,
)
FILENAME_VERSION_PATTERN = re.compile(rf"(?:^|[_-])v?{VERSION_VALUE}(?:[_-]|\.|$)", re.IGNORECASE)


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
    if category == "windows" and len(content) > MAX_WINDOWS_SCRIPT_BYTES:
        raise ScriptValidationError("Windows script must not exceed 2 MiB")

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
    content, encoding = decode_text_content(raw[:max_bytes])
    return {
        **record,
        "content": content,
        "truncated": truncated,
        "encoding": encoding,
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
    record: dict[str, object] = {
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
        "content_version": None,
        "filename_version": None,
        "version_consistent": None,
        "sha256": None,
        "encoding": None,
    }
    if physical_category == "windows":
        record.update(build_windows_script_metadata(resolved))
    return record


def build_windows_script_metadata(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    content, encoding = decode_text_content(raw[:64 * 1024])
    content_version = extract_content_version(content)
    filename_version = extract_filename_version(path.name)
    version_consistent = (
        content_version == filename_version
        if content_version is not None and filename_version is not None
        else None
    )
    return {
        "content_version": content_version,
        "filename_version": filename_version,
        "version_consistent": version_consistent,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "encoding": encoding,
    }


def decode_text_content(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace"), "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16", errors="replace"), "utf-16le"
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace"), "utf-16be"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        try:
            return raw.decode("gb18030"), "gb18030"
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def extract_content_version(content: str) -> str | None:
    for pattern in (SCRIPT_VERSION_PATTERN, SCRIPT_HEADER_VERSION_PATTERN):
        match = pattern.search(content)
        if match:
            return f"v{match.group('version')}"
    return None


def extract_filename_version(name: str) -> str | None:
    match = FILENAME_VERSION_PATTERN.search(name)
    return f"v{match.group('version')}" if match else None


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
    if relative.parts and relative.parts[0] == "windows":
        return "windows"
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
