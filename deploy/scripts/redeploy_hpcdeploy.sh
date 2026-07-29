#!/usr/bin/env bash
set -euo pipefail

SCRIPT_VERSION="1.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common_runtime.sh"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
LEGACY_FRONTEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-frontend.service"
NGINX_SITE_DEST="/etc/nginx/conf.d/hpcdeploy.conf"
WEB_ROOT="/var/www/hpcdeploy"

run_as_service_user() {
  if [[ "$SERVICE_USER" == "root" ]]; then
    env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  else
    sudo -H -u "$SERVICE_USER" env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  fi
}

assert_no_active_tasks() {
  local payload
  local active_count
  local active_task_id
  if ! payload="$(curl --noproxy '*' --fail --silent --show-error \
    'http://127.0.0.1:8000/api/tasks?active_only=true&limit=1' 2>/dev/null)"; then
    echo "后端当前不可查询活动任务；继续执行发布以允许故障恢复。"
    return
  fi
  read -r active_count active_task_id < <(
    python3 -c 'import json, sys; data=json.load(sys.stdin); items=data.get("items") or []; print(int(data.get("total") or 0), items[0].get("task_id", "-") if items else "-")' \
      <<< "$payload"
  )
  if (( active_count > 0 )); then
    echo "检测到活动任务，拒绝重启后端：count=$active_count task_id=$active_task_id" >&2
    echo "请等待任务结束或取消任务后重新发布。" >&2
    exit 1
  fi
}

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 执行更新："
  echo "  sudo deploy/scripts/redeploy_hpcdeploy.sh"
  echo "将执行："
  echo "  backend/.deps/bin/pip install -r backend/requirements.txt"
  echo "  cd frontend && npm install/npm ci && npm run build"
  echo "  发布 frontend/dist 到 /var/www/hpcdeploy"
  echo "  systemctl restart hpcdeploy-backend"
  echo "  nginx -t && systemctl reload nginx"
  exit 0
fi

assert_no_active_tasks

NODE_BIN_DIR="$(resolve_service_node_bin "$SERVICE_USER")"
echo "使用 Node.js：$NODE_BIN_DIR/node ($("$NODE_BIN_DIR/node" --version))"

if [[ ! -x "$BACKEND_DIR/.deps/bin/python" ]]; then
  run_as_service_user python3 -m venv "$BACKEND_DIR/.deps"
fi
run_as_service_user "$BACKEND_DIR/.deps/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

cd "$FRONTEND_DIR"
if [[ -f package-lock.json ]]; then
  run_as_service_user npm ci
else
  run_as_service_user npm install
fi
run_as_service_user npm run build

install -d -m 755 "$WEB_ROOT"
cp -a "$FRONTEND_DIR/dist/." "$WEB_ROOT/"
find "$WEB_ROOT" -type d -exec chmod 755 {} +
find "$WEB_ROOT" -type f -exec chmod 644 {} +
install -D -m 644 "$PROJECT_ROOT/deploy/nginx/hpcdeploy.conf" "$NGINX_SITE_DEST"
nginx -t

if systemctl list-unit-files hpcdeploy-frontend.service >/dev/null 2>&1; then
  systemctl disable --now hpcdeploy-frontend.service || true
fi
if [[ -f "$LEGACY_FRONTEND_SERVICE_DEST" ]]; then
  rm -f "$LEGACY_FRONTEND_SERVICE_DEST"
  systemctl daemon-reload
fi

assert_no_active_tasks
systemctl restart hpcdeploy-backend
wait_for_backend_health
systemctl reload nginx

echo "HPCDeploy 已更新并重启完成"
echo "更新脚本版本：$SCRIPT_VERSION"
echo "项目目录：$PROJECT_ROOT"
echo "访问地址：http://<server-ip>:10086/"
