#!/usr/bin/env bash
set -euo pipefail

SCRIPT_VERSION="1.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common_runtime.sh"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-backend.service"
LEGACY_FRONTEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-frontend.service"
NGINX_SITE_DEST="/etc/nginx/conf.d/hpcdeploy.conf"
NGINX_DEFAULT_SITE="/etc/nginx/sites-enabled/default"
WEB_ROOT="/var/www/hpcdeploy"
HPCDEPLOY_CONFIG_DIR="/etc/hpcdeploy"
HPCDEPLOY_ENV_FILE="/etc/hpcdeploy/hpcdeploy.env"
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
    env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  else
    sudo -H -u "$SERVICE_USER" env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1"
    exit 1
  fi
}

configure_security_environment() {
  local admin_password=""
  local admin_password_confirm=""
  local secret_key=""

  install -d -m 700 -o root -g root "$HPCDEPLOY_CONFIG_DIR"
  if [[ -f "$HPCDEPLOY_ENV_FILE" ]]; then
    chmod 600 "$HPCDEPLOY_ENV_FILE"
    if ! grep -q '^SECRET_KEY=.' "$HPCDEPLOY_ENV_FILE" \
      || ! grep -q '^HPCDEPLOY_ADMIN_PASSWORD=.' "$HPCDEPLOY_ENV_FILE"; then
      echo "安全配置不完整：$HPCDEPLOY_ENV_FILE" >&2
      echo "请修复 SECRET_KEY 和 HPCDEPLOY_ADMIN_PASSWORD 后重新安装。" >&2
      exit 1
    fi
    echo "保留现有安全配置：$HPCDEPLOY_ENV_FILE"
    return
  fi

  secret_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  if [[ -n "${HPCDEPLOY_ADMIN_PASSWORD:-}" ]]; then
    admin_password="$HPCDEPLOY_ADMIN_PASSWORD"
  elif [[ -t 0 ]]; then
    while true; do
      read -r -s -p "请设置管理员密码（至少 6 位）：" admin_password
      printf '\n'
      read -r -s -p "请再次输入管理员密码：" admin_password_confirm
      printf '\n'
      if [[ ${#admin_password} -lt 6 ]]; then
        echo "管理员密码至少需要 6 位。"
      elif [[ "$admin_password" != "$admin_password_confirm" ]]; then
        echo "两次输入的管理员密码不一致。"
      else
        break
      fi
    done
  else
    admin_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
    GENERATED_ADMIN_PASSWORD="$admin_password"
  fi

  if [[ ${#admin_password} -lt 6 || "$admin_password" == *$'\n'* || "$admin_password" == *$'\r'* ]]; then
    echo "HPCDEPLOY_ADMIN_PASSWORD 必须至少 6 位且不能包含换行符。" >&2
    exit 1
  fi

  umask 077
  admin_password="${admin_password//\\/\\\\}"
  admin_password="${admin_password//\"/\\\"}"
  {
    printf 'APP_ENV=production\n'
    printf 'SECRET_KEY=%s\n' "$secret_key"
    printf 'HPCDEPLOY_ADMIN_PASSWORD="%s"\n' "$admin_password"
  } > "$HPCDEPLOY_ENV_FILE"
  chown root:root "$HPCDEPLOY_ENV_FILE"
  chmod 600 "$HPCDEPLOY_ENV_FILE"
  echo "已生成安全配置：$HPCDEPLOY_ENV_FILE"
}

install_prerequisites

require_cmd python3
require_cmd npm
require_cmd nginx
require_cmd systemctl

configure_security_environment

NODE_BIN_DIR="$(resolve_service_node_bin "$SERVICE_USER")"
echo "使用 Node.js：$NODE_BIN_DIR/node ($("$NODE_BIN_DIR/node" --version))"

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
EnvironmentFile=/etc/hpcdeploy/hpcdeploy.env
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
wait_for_backend_health
systemctl restart nginx

if systemctl list-unit-files hpcdeploy-frontend.service >/dev/null 2>&1; then
  systemctl disable --now hpcdeploy-frontend.service || true
fi
if [[ -f "$LEGACY_FRONTEND_SERVICE_DEST" ]]; then
  rm -f "$LEGACY_FRONTEND_SERVICE_DEST"
  systemctl daemon-reload
fi

echo "HPCDeploy 服务安装完成"
echo "安装脚本版本：$SCRIPT_VERSION"
echo "项目目录：$PROJECT_ROOT"
echo "服务用户：$SERVICE_USER:$SERVICE_GROUP"
echo "后端服务：systemctl status hpcdeploy-backend"
echo "Web 服务：systemctl status nginx"
echo "访问地址：http://<server-ip>:10086/"
if [[ -n "${GENERATED_ADMIN_PASSWORD:-}" ]]; then
  echo "非交互安装生成的管理员密码（仅显示本次）：$GENERATED_ADMIN_PASSWORD"
fi
echo "忘记管理员密码时执行：sudo $PROJECT_ROOT/deploy/scripts/reset_admin_password.sh"
