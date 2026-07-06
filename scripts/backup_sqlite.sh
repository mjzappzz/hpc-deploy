#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_PATH="${HPCDEPLOY_DB_PATH:-$PROJECT_ROOT/backend/data/hpc_control_panel.db}"
BACKUP_DIR="${1:-$PROJECT_ROOT/backend/data/backups}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "数据库不存在：$DB_PATH"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_path="$BACKUP_DIR/hpc_control_panel_$timestamp.db"

python3 - "$DB_PATH" "$backup_path" <<'PY'
import sqlite3
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
dst.parent.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(src) as source:
    with sqlite3.connect(dst) as target:
        source.backup(target)
PY

chmod 600 "$backup_path" 2>/dev/null || true

echo "SQLite 备份完成：$backup_path"
ls -lh "$backup_path"
