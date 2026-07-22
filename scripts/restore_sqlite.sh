#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  scripts/restore_sqlite.sh <backup-db-path> --force

说明：
  - 默认恢复到 backend/data/hpc_control_panel.db
  - 可通过 HPCDEPLOY_DB_PATH 指定目标数据库路径
  - 未加 --force 时只展示将执行的操作
  - 恢复前会备份当前数据库到 backend/data/backups/pre_restore_<timestamp>.db
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_PATH="${HPCDEPLOY_DB_PATH:-$PROJECT_ROOT/backend/data/hpc_control_panel.db}"
BACKUP_PATH="${1:-}"
FORCE="${2:-}"
SAFETY_BACKUP_DIR="$PROJECT_ROOT/backend/data/backups"

if [[ -z "$BACKUP_PATH" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "备份文件不存在：$BACKUP_PATH"
  exit 1
fi

if [[ "$FORCE" != "--force" ]]; then
  echo "将恢复：$BACKUP_PATH"
  echo "目标库：$DB_PATH"
  echo "当前为 dry-run，未执行覆盖。确认后加 --force："
  echo "  sudo scripts/restore_sqlite.sh \"$BACKUP_PATH\" --force"
  exit 0
fi

stop_service_if_available() {
  local name="$1"
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$name" >/dev/null 2>&1; then
    systemctl stop "$name" 2>/dev/null || true
  fi
}

start_service_if_available() {
  local name="$1"
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$name" >/dev/null 2>&1; then
    systemctl start "$name" 2>/dev/null || true
  fi
}

mkdir -p "$(dirname "$DB_PATH")" "$SAFETY_BACKUP_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
safety_backup="$SAFETY_BACKUP_DIR/pre_restore_$timestamp.db"

stop_service_if_available hpcdeploy-backend.service

if [[ -f "$DB_PATH" ]]; then
  cp -a "$DB_PATH" "$safety_backup"
  chmod 600 "$safety_backup" 2>/dev/null || true
  echo "当前数据库已安全备份：$safety_backup"
fi

cp -a "$BACKUP_PATH" "$DB_PATH"
chmod 600 "$DB_PATH" 2>/dev/null || true

start_service_if_available hpcdeploy-backend.service

echo "SQLite 恢复完成：$DB_PATH"
