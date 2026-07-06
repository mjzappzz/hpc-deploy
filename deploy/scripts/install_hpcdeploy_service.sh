#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-backend.service"
FRONTEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-frontend.service"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

if [[ $EUID -ne 0 ]]; then
  echo "请使用 root 或 sudo 执行此脚本"
  exit 1
fi

install_prerequisites() {
  local missing=()
  local cmd
  for cmd in python3 npm systemctl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done

  if ! python3 -m venv --help >/dev/null 2>&1; then
    missing+=("python3-venv")
  fi

  if [[ ${#missing[@]} -eq 0 ]]; then
    return
  fi

  echo "检测到缺少依赖：${missing[*]}"
  echo "开始安装基础依赖..."

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 \
      python3-venv \
      python3-pip \
      nodejs \
      npm
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y \
      python3 \
      python3-pip \
      nodejs \
      npm
  elif command -v yum >/dev/null 2>&1; then
    yum install -y \
      python3 \
      python3-pip \
      nodejs \
      npm
  else
    echo "未检测到 apt-get/dnf/yum，无法自动安装依赖。"
    echo "请手动安装：python3 python3-venv python3-pip nodejs npm systemd"
    exit 1
  fi
}

run_as_service_user() {
  if [[ "$SERVICE_USER" == "root" ]]; then
    "$@"
  else
    sudo -H -u "$SERVICE_USER" "$@"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1"
    exit 1
  fi
}

install_prerequisites

require_cmd python3
require_cmd npm
require_cmd systemctl

install -d -m 755 -o "$SERVICE_USER" -g "$SERVICE_GROUP" \
  "$BACKEND_DIR/data" \
  "$BACKEND_DIR/data/artifacts" \
  "$BACKEND_DIR/keys" \
  "$BACKEND_DIR/apptainer"

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

cat > "$BACKEND_SERVICE_DEST" <<EOF
[Unit]
Description=HPCDeploy FastAPI Backend
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$BACKEND_DIR
Environment=PYTHONPATH=$BACKEND_DIR/.deps:$BACKEND_DIR
ExecStart=$BACKEND_DIR/.deps/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > "$FRONTEND_SERVICE_DEST" <<EOF
[Unit]
Description=HPCDeploy Vue Frontend (Vite Dev Server)
After=network.target hpcdeploy-backend.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$FRONTEND_DIR
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 5173
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hpcdeploy-backend
systemctl enable hpcdeploy-frontend
systemctl restart hpcdeploy-backend
systemctl restart hpcdeploy-frontend

echo "HPCDeploy 服务安装完成"
echo "项目目录：$PROJECT_ROOT"
echo "服务用户：$SERVICE_USER:$SERVICE_GROUP"
echo "后端服务：systemctl status hpcdeploy-backend"
echo "前端服务：systemctl status hpcdeploy-frontend"
echo "访问地址：http://<server-ip>:5173"
