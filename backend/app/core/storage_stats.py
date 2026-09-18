from __future__ import annotations

import os
from pathlib import Path

from app.schemas.dashboard import StorageBreakdownItem


def collect_directory_size(path: Path, excluded: set[Path] | None = None) -> int:
    """Return regular-file bytes under path without following symlinked directories."""
    if not path.exists():
        return 0
    excluded = {item.resolve(strict=False) for item in (excluded or set())}
    total = 0
    for current, directories, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        if current_path.resolve(strict=False) in excluded:
            directories[:] = []
            continue
        directories[:] = [name for name in directories if (current_path / name).resolve(strict=False) not in excluded]
        for name in files:
            file_path = current_path / name
            try:
                if file_path.resolve(strict=False) in excluded:
                    continue
                if file_path.is_file() and not file_path.is_symlink():
                    total += file_path.stat().st_size
            except OSError:
                continue
    return total


def collect_storage_breakdown(
    *,
    project_root: Path,
    database_path: Path,
    artifacts_path: Path,
    backups_path: Path,
    gpu_library_path: Path,
) -> list[StorageBreakdownItem]:
    data_root = database_path.parent
    known_data_paths = {artifacts_path, backups_path, gpu_library_path}
    try:
        database_bytes = database_path.stat().st_size if database_path.is_file() else 0
    except OSError:
        database_bytes = 0
    items = [
        StorageBreakdownItem(key="artifacts", label="任务产物", path=str(artifacts_path), size_bytes=collect_directory_size(artifacts_path)),
        StorageBreakdownItem(key="sqlite_database", label="SQLite 数据库", path=str(database_path), size_bytes=database_bytes),
        StorageBreakdownItem(key="sqlite_backups", label="SQLite 备份", path=str(backups_path), size_bytes=collect_directory_size(backups_path)),
        StorageBreakdownItem(key="gpu_driver_library", label="GPU 驱动库", path=str(gpu_library_path), size_bytes=collect_directory_size(gpu_library_path)),
        StorageBreakdownItem(
            key="controller_data_other",
            label="其他 HPCDeploy 数据",
            path=str(data_root),
            size_bytes=collect_directory_size(data_root, known_data_paths | {database_path}),
        ),
        StorageBreakdownItem(
            key="project_runtime",
            label="项目/运行时文件",
            path=str(project_root),
            size_bytes=collect_directory_size(project_root, {data_root}),
        ),
    ]
    for item in items:
        if not item.path:
            continue
        path = Path(item.path)
        try:
            if not path.exists():
                item.status = "unavailable"
                item.error = "path not found"
            elif not os.access(path, os.R_OK):
                item.status = "unavailable"
                item.error = "permission denied"
            elif path.is_dir():
                next(path.iterdir(), None)
        except OSError as exc:
            item.status = "partial"
            item.error = str(exc)
    return items


def resolve_mount_metadata(path: Path) -> tuple[str | None, str | None]:
    """Resolve the longest matching mount entry from Linux mountinfo."""
    try:
        target = Path(os.path.realpath(path))
        entries: list[tuple[Path, str]] = []
        for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
            before, separator, after = line.partition(" - ")
            if not separator:
                continue
            fields = before.split()
            post_fields = after.split()
            if len(fields) < 5 or len(post_fields) < 2:
                continue
            mountpoint = _unescape_mountinfo(fields[4])
            source = _unescape_mountinfo(post_fields[1])
            entries.append((Path(mountpoint), source))
        matches = [(mountpoint, source) for mountpoint, source in entries if _is_within(target, mountpoint)]
        if not matches:
            return None, None
        mountpoint, source = max(matches, key=lambda item: len(str(item[0])))
        return source, str(mountpoint)
    except OSError:
        return None, None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _unescape_mountinfo(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
