#!/usr/bin/env bash
set -euo pipefail

SCRIPT_VERSION="1.0.0"
umask 077
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common_runtime.sh"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATABASE_PATH="$PROJECT_ROOT/backend/data/hpc_control_panel.db"
BACKUP_DIR="$PROJECT_ROOT/backend/data/backups"
HPCDEPLOY_ENV_FILE="/etc/hpcdeploy/hpcdeploy.env"

if [[ $EUID -ne 0 ]]; then
  echo "请使用 root 权限执行：sudo $0" >&2
  exit 1
fi

if [[ ! -f "$HPCDEPLOY_ENV_FILE" ]]; then
  echo "安全配置不存在：$HPCDEPLOY_ENV_FILE" >&2
  echo "请先重新执行安装脚本初始化安全配置。" >&2
  exit 1
fi

new_password=""
new_password_confirm=""
while true; do
  read -r -s -p "请输入新的管理员密码（至少 6 位）：" new_password
  printf '\n'
  read -r -s -p "请再次输入新的管理员密码：" new_password_confirm
  printf '\n'
  if [[ ${#new_password} -lt 6 ]]; then
    echo "管理员密码至少需要 6 位。"
  elif [[ "$new_password" != "$new_password_confirm" ]]; then
    echo "两次输入的管理员密码不一致。"
  else
    break
  fi
done

new_secret_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_path="$BACKUP_DIR/pre_admin_reset_${timestamp}.db"

install -d -m 700 "$BACKUP_DIR"
if [[ -f "$DATABASE_PATH" ]]; then
  python3 - "$DATABASE_PATH" "$backup_path" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1:3]
with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as backup:
    source.backup(backup)
    table_exists = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'system_settings'"
    ).fetchone()
    if table_exists:
        source.execute("DELETE FROM system_settings WHERE key = 'admin_password'")
        source.commit()
PY
  chmod 600 "$backup_path"
  echo "数据库安全备份：$backup_path"
else
  echo "数据库尚不存在，跳过数据库密码覆盖清理。"
fi

python3 - "$HPCDEPLOY_ENV_FILE" "$new_password" "$new_secret_key" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

env_path = Path(sys.argv[1])
new_password = sys.argv[2]
new_secret_key = sys.argv[3]
updates = {
    "APP_ENV": "production",
    "HPCDEPLOY_ADMIN_PASSWORD": new_password,
    "SECRET_KEY": new_secret_key,
}

def encode_env_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

lines = env_path.read_text(encoding="utf-8").splitlines()
seen: set[str] = set()
output: list[str] = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        output.append(f"{key}={encode_env_value(updates[key])}")
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={encode_env_value(value)}")

fd, temporary = tempfile.mkstemp(prefix=".hpcdeploy.env.", dir=env_path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, env_path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
chown root:root "$HPCDEPLOY_ENV_FILE"
chmod 600 "$HPCDEPLOY_ENV_FILE"

systemctl restart hpcdeploy-backend
wait_for_backend_health

echo "管理员密码已重置。"
echo "重置脚本版本：$SCRIPT_VERSION"
echo "现有管理员会话已失效，请使用新密码重新进入管理员模式。"
