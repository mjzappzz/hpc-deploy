#!/usr/bin/env python3
"""Back up and compact historical noisy task logs.

Usage:
  PYTHONPATH=backend python3 backend/tools/compact_historical_logs.py --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.artifact_collector import _compact_log_file  # noqa: E402

DATA_ROOT = BACKEND_ROOT / "data"
DEFAULT_DATABASE = DATA_ROOT / "hpc_control_panel.db"
DEFAULT_ARTIFACTS = DATA_ROOT / "artifacts"
WGET_PROGRESS_LINE = re.compile(r"^\s*\d+(?:\.\d+)?[KMG]?\s+(?:\.{10}\s+){2,}\d+%")
NOISY_LEVELS = {"INFO", "STDERR", "WARN"}


def _is_noisy_task_log(level: str, message: str) -> bool:
    return level in NOISY_LEVELS and ("\r" in message or bool(WGET_PROGRESS_LINE.match(message)))


def _database_noise_stats(database: Path) -> tuple[int, int]:
    count = 0
    byte_count = 0
    with sqlite3.connect(database) as conn:
        for level, message in conn.execute("SELECT level, message FROM task_logs"):
            text = message or ""
            if _is_noisy_task_log(level or "", text):
                count += 1
                byte_count += len(text.encode("utf-8"))
    return count, byte_count


def _artifact_log_files(artifacts_root: Path) -> list[Path]:
    return sorted(path for path in artifacts_root.rglob("*.log") if path.is_file())


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as input_db, sqlite3.connect(destination) as output_db:
        input_db.backup(output_db)


def _backup_artifact_logs(artifacts_root: Path, destination_root: Path, paths: list[Path]) -> None:
    for path in paths:
        destination = destination_root / path.relative_to(artifacts_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _delete_noisy_task_logs_and_vacuum(database: Path) -> int:
    deleted = 0
    with sqlite3.connect(database) as conn:
        cursor = conn.execute("SELECT id, level, message FROM task_logs")
        batch: list[tuple[int]] = []
        for log_id, level, message in cursor:
            if _is_noisy_task_log(level or "", message or ""):
                batch.append((log_id,))
            if len(batch) >= 5000:
                conn.executemany("DELETE FROM task_logs WHERE id = ?", batch)
                deleted += len(batch)
                batch.clear()
        if batch:
            conn.executemany("DELETE FROM task_logs WHERE id = ?", batch)
            deleted += len(batch)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create backups and perform compaction")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS)
    args = parser.parse_args()

    database = args.database.resolve()
    artifacts_root = args.artifacts_root.resolve()
    if not database.is_file():
        raise SystemExit(f"database not found: {database}")
    if not artifacts_root.is_dir():
        raise SystemExit(f"artifacts root not found: {artifacts_root}")

    noisy_rows, noisy_bytes = _database_noise_stats(database)
    log_files = _artifact_log_files(artifacts_root)
    artifact_bytes = sum(path.stat().st_size for path in log_files)
    print(f"database_noise_rows={noisy_rows}")
    print(f"database_noise_message_bytes={noisy_bytes}")
    print(f"artifact_log_files={len(log_files)}")
    print(f"artifact_log_bytes_before={artifact_bytes}")
    if not args.apply:
        print("dry_run=true")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = DATA_ROOT / "backups" / f"log-compaction-{timestamp}"
    database_backup = backup_root / database.name
    artifact_backup_root = backup_root / "artifacts-log"
    _backup_database(database, database_backup)
    _backup_artifact_logs(artifacts_root, artifact_backup_root, log_files)
    print(f"backup_root={backup_root}")

    compacted_files = sum(1 for path in log_files if _compact_log_file(path))
    artifact_bytes_after = sum(path.stat().st_size for path in log_files)
    deleted_rows = _delete_noisy_task_logs_and_vacuum(database)
    print(f"artifact_log_files_compacted={compacted_files}")
    print(f"artifact_log_bytes_after={artifact_bytes_after}")
    print(f"artifact_log_bytes_reclaimed={artifact_bytes - artifact_bytes_after}")
    print(f"database_rows_deleted={deleted_rows}")
    print(f"database_bytes_after={database.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
