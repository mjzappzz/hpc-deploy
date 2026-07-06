#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
SERVICE_USER="${SUDO_USER:-$(id -un)}"

run_as_service_user() {
  if [[ "$SERVICE_USER" == "root" ]]; then
    "$@"
  else
    sudo -H -u "$SERVICE_USER" "$@"
  fi
}

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 执行更新："
  echo "  sudo deploy/scripts/redeploy_hpcdeploy.sh"
  echo "将执行："
  echo "  backend/.deps/bin/pip install -r backend/requirements.txt"
  echo "  cd frontend && npm install/npm ci"
  echo "  systemctl restart hpcdeploy-backend"
  echo "  systemctl restart hpcdeploy-frontend"
  exit 0
fi

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

systemctl restart hpcdeploy-backend
systemctl restart hpcdeploy-frontend

echo "HPCDeploy 已更新并重启完成"
echo "项目目录：$PROJECT_ROOT"
