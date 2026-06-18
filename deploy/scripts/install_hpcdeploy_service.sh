#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/tjzs/projects/hpc-deploy"
BACKEND_SERVICE_SRC="$PROJECT_ROOT/deploy/systemd/hpcdeploy-backend.service"
BACKEND_SERVICE_DEST="/etc/systemd/system/hpcdeploy-backend.service"
NGINX_CONF_SRC="$PROJECT_ROOT/deploy/nginx/hpcdeploy.conf"
NGINX_CONF_DEST="/etc/nginx/conf.d/hpcdeploy.conf"
WEB_ROOT="/var/www/hpcdeploy"

if [[ $EUID -ne 0 ]]; then
  echo "请使用 root 或 sudo 执行此脚本"
  exit 1
fi

install -d -m 755 "$WEB_ROOT"
cp "$BACKEND_SERVICE_SRC" "$BACKEND_SERVICE_DEST"
cp "$NGINX_CONF_SRC" "$NGINX_CONF_DEST"

systemctl daemon-reload
systemctl enable hpcdeploy-backend
systemctl restart hpcdeploy-backend
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "HPCDeploy 服务安装完成"
echo "后端服务：systemctl status hpcdeploy-backend"
echo "Nginx 配置：$NGINX_CONF_DEST"
