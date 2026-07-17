import os
import re
import stat
import zipfile
from pathlib import Path

from app.models.task_log import TaskLog

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_ROOT / "data" / "artifacts"

ALLOWED_EXTENSIONS = {".log", ".txt", ".csv", ".xlsx", ".json"}
WGET_PROGRESS_LINE = re.compile(r"^\s*\d+(?:\.\d+)?[KMG]?\s+(?:\.{10}\s+){2,}\d+%")
PERCENT_PROGRESS_LINE = re.compile(r"^\s*(\d+(?:\.\d+)?)%")


def collect_artifacts(
    db,
    task_id: str,
    remote_work_dir: str | None,
    executor,
) -> list[str]:
    """Download allowed artifacts from remote work dir to local artifacts dir.

    Args:
        db: SQLAlchemy database session.
        task_id: The task identifier (e.g. "task-20260617-123504-fa211d").
        remote_work_dir: Remote directory path on the target server.
        executor: SSHExecutor instance with an active SFTP session.

    Returns:
        List of downloaded filenames (local basenames).
    """
    if not remote_work_dir:
        _add_log(db, task_id, "SYSTEM", "artifact collection skipped: no remote_work_dir")
        return []

    local_dir = ARTIFACTS_DIR / task_id
    local_dir.mkdir(parents=True, exist_ok=True)
    _add_log(db, task_id, "SYSTEM", f"collecting artifacts from {remote_work_dir}")

    # --- list remote files ---
    try:
        remote_entries = executor.sftp.listdir_attr(remote_work_dir)
    except Exception as exc:
        _add_log(db, task_id, "ERROR", f"failed to list remote directory: {exc}")
        return []

    candidates = []
    for attr in remote_entries:
        # skip dirs and symlinks
        if stat.S_ISDIR(attr.st_mode) or stat.S_ISLNK(attr.st_mode):
            continue
        candidates.append(attr.filename)

    allowed = [f for f in candidates if _is_allowed_artifact(f)]

    if not allowed:
        _add_log(db, task_id, "SYSTEM", "no artifacts found")
        return []

    # --- download ---
    downloaded = []
    errors = []
    for filename in allowed:
        safe = _safe_basename(filename)
        if safe is None:
            errors.append(filename)
            _add_log(db, task_id, "ERROR", f"artifact skipped (unsafe name): {filename}")
            continue

        remote_path = f"{remote_work_dir.rstrip('/')}/{safe}"
        local_path = local_dir / safe
        temp_path = local_dir / f".{safe}.part"

        try:
            executor.sftp.get(remote_path, str(temp_path))
            if local_path.suffix.lower() == ".xlsx":
                _validate_xlsx(temp_path)
            os.replace(temp_path, local_path)
            downloaded.append(safe)
            _add_log(db, task_id, "SYSTEM", f"artifact downloaded: {safe}")
            if local_path.suffix.lower() == ".log" and _compact_log_file(local_path):
                _add_log(db, task_id, "SYSTEM", f"artifact log compacted: {safe}")
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            errors.append(safe)
            _add_log(db, task_id, "ERROR", f"artifact download failed: {safe} - {exc}")

    if downloaded:
        _add_log(db, task_id, "SYSTEM", f"artifact collection completed, {len(downloaded)} files")

    if errors:
        _add_log(
            db, task_id, "ERROR",
            f"artifact collection partially failed: {', '.join(errors)}",
        )

    return downloaded


def _is_allowed_artifact(filename: str) -> bool:
    """Return True if *filename* should be collected as an artifact."""
    if filename.startswith("."):
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _safe_basename(filename: str) -> str | None:
    """Return the basename if it is safe, otherwise None."""
    name = os.path.basename(filename)
    if not name or name != filename:
        return None
    if name.startswith("."):
        return None
    if ".." in name:
        return None
    if "/" in name:
        return None
    return name


def _validate_xlsx(path: Path) -> None:
    """Raise when an XLSX artifact is not a complete ZIP container."""
    try:
        with zipfile.ZipFile(path) as workbook:
            bad_member = workbook.testzip()
    except zipfile.BadZipFile as exc:
        raise ValueError("incomplete or invalid XLSX artifact") from exc
    if bad_member:
        raise ValueError(f"corrupt XLSX member: {bad_member}")


def _compact_log_file(path: Path) -> bool:
    """Remove high-frequency progress rows from a recovered log in place.

    Stage messages, errors, one sample per 10% progress bucket, and normal output
    are retained. The replacement is atomic and the original is kept unchanged
    when no compaction is needed.
    """
    compact_path = path.with_name(f".{path.name}.compact")
    changed = False
    skipped_progress = 0
    sampled_buckets: set[int] = set()
    previous_line: str | None = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as source, compact_path.open(
            "w", encoding="utf-8"
        ) as target:
            for raw_line in source:
                line = raw_line.rstrip("\r\n")
                if "\r" in line:
                    skipped_progress += line.count("\r")
                    line = line.rsplit("\r", 1)[-1]
                    changed = True

                if WGET_PROGRESS_LINE.match(line):
                    skipped_progress += 1
                    changed = True
                    continue

                progress_match = PERCENT_PROGRESS_LINE.match(line)
                if progress_match:
                    bucket = int(float(progress_match.group(1)) // 10)
                    if bucket in sampled_buckets:
                        skipped_progress += 1
                        changed = True
                        continue
                    sampled_buckets.add(bucket)

                if line == previous_line:
                    skipped_progress += 1
                    changed = True
                    continue

                target.write(f"{line}\n")
                previous_line = line

            if skipped_progress:
                target.write(
                    f"[INFO] 已省略 {skipped_progress} 条高频进度/重复输出；保留阶段、错误和进度样本。\n"
                )

        if changed:
            os.replace(compact_path, path)
            return True
        compact_path.unlink(missing_ok=True)
        return False
    except Exception:
        compact_path.unlink(missing_ok=True)
        raise


def _add_log(db, task_id: str, level: str, message: str) -> None:
    db.add(TaskLog(task_id=task_id, level=level, message=message))
    db.commit()
