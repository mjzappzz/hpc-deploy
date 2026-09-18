from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.schemas.dashboard import StorageBreakdownItem


@dataclass
class ProjectStorageResult:
    project_total_bytes: int
    project_total_file_count: int
    complete: bool
    items: list[StorageBreakdownItem]


def collect_project_storage(
    *, project_root: Path, modules: list[tuple[str, str, Path]] | tuple[tuple[str, str, Path], ...],
) -> ProjectStorageResult:
    excluded = {path.resolve(strict=False) for _, _, path in modules if path.is_dir()}
    excluded.update(path.resolve(strict=False) for _, _, path in modules if path.is_file())
    items: list[StorageBreakdownItem] = []
    complete = True
    for key, label, path in modules:
        size_bytes, file_count, status, error = _measure_path(path)
        complete = complete and status == "available"
        items.append(StorageBreakdownItem(key=key, label=label, path=str(path), size_bytes=size_bytes, file_count=file_count, status=status, error=error))

    other_size, other_count, other_status, other_error = _measure_path(project_root, excluded=excluded)
    complete = complete and other_status == "available"
    items.append(StorageBreakdownItem(key="other_project_runtime", label="其他项目运行文件", path=str(project_root), size_bytes=other_size, file_count=other_count, status=other_status, error=other_error))
    total_bytes = sum(item.size_bytes for item in items)
    total_file_count = sum(item.file_count for item in items)
    for item in items:
        item.percentage = item.size_bytes / total_bytes * 100 if item.status == "available" and total_bytes else None
    return ProjectStorageResult(total_bytes, total_file_count, complete, items)


def _measure_path(path: Path, excluded: set[Path] | None = None) -> tuple[int, int, str, str | None]:
    if not path.exists():
        return 0, 0, "unavailable", "path not found"
    try:
        if path.is_file():
            return path.stat().st_size, 1, "available", None
        if not os.access(path, os.R_OK):
            return 0, 0, "unavailable", "permission denied"
        total = 0
        count = 0
        errors: list[str] = []
        excluded = excluded or set()

        def onerror(error: OSError) -> None:
            errors.append(str(error))

        for current, directories, files in os.walk(path, followlinks=False, onerror=onerror):
            current_path = Path(current)
            if current_path.resolve(strict=False) in excluded:
                directories[:] = []
                continue
            directories[:] = [name for name in directories if (current_path / name).resolve(strict=False) not in excluded]
            for name in files:
                file_path = current_path / name
                try:
                    if file_path.resolve(strict=False) in excluded or file_path.is_symlink() or not file_path.is_file():
                        continue
                    total += file_path.stat().st_size
                    count += 1
                except OSError as error:
                    errors.append(str(error))
        return total, count, "partial" if errors else "available", errors[0] if errors else None
    except OSError as error:
        return 0, 0, "partial", str(error)
