#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-backend.service"
LEGACY_FRONTEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-frontend.service"
NGINX_SITE_DEST="/etc/nginx/conf.d/hpcdeploy.conf"
NGINX_DEFAULT_SITE="/etc/nginx/sites-enabled/default"
WEB_ROOT="/var/www/hpcdeploy"
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
  for cmd in python3 npm systemctl nginx; do
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
      npm \
      nginx
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y \
      python3 \
      python3-pip \
      nodejs \
      npm \
      nginx
  elif command -v yum >/dev/null 2>&1; then
    yum install -y \
      python3 \
      python3-pip \
      nodejs \
      npm \
      nginx
  else
    echo "未检测到 apt-get/dnf/yum，无法自动安装依赖。"
    echo "请手动安装：python3 python3-venv python3-pip nodejs npm nginx systemd"
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
require_cmd nginx
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
run_as_service_user npm run build

install -d -m 755 "$WEB_ROOT"
cp -a "$FRONTEND_DIR/dist/." "$WEB_ROOT/"
find "$WEB_ROOT" -type d -exec chmod 755 {} +
find "$WEB_ROOT" -type f -exec chmod 644 {} +

install -D -m 644 "$PROJECT_ROOT/deploy/nginx/hpcdeploy.conf" "$NGINX_SITE_DEST"
if [[ -L "$NGINX_DEFAULT_SITE" ]]; then
  unlink "$NGINX_DEFAULT_SITE"
fi
nginx -t

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

systemctl daemon-reload
systemctl enable hpcdeploy-backend
systemctl enable nginx
systemctl restart hpcdeploy-backend
systemctl restart nginx

if systemctl list-unit-files hpcdeploy-frontend.service >/dev/null 2>&1; then
  systemctl disable --now hpcdeploy-frontend.service || true
fi
if [[ -f "$LEGACY_FRONTEND_SERVICE_DEST" ]]; then
  rm -f "$LEGACY_FRONTEND_SERVICE_DEST"
  systemctl daemon-reload
fi

echo "HPCDeploy 服务安装完成"
echo "项目目录：$PROJECT_ROOT"
echo "服务用户：$SERVICE_USER:$SERVICE_GROUP"
echo "后端服务：systemctl status hpcdeploy-backend"
echo "Web 服务：systemctl status nginx"
echo "访问地址：http://<server-ip>:10086/"
