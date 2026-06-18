#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/tjzs/projects/hpc-deploy"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
WEB_ROOT="/var/www/hpcdeploy"

cd "$FRONTEND_DIR"
npm run build

if [[ $EUID -ne 0 ]]; then
  echo "前端已构建完成。请使用 sudo 执行以下命令发布："
  echo "  rsync -av --delete \"$FRONTEND_DIR/dist/\" \"$WEB_ROOT/\""
  echo "  systemctl restart hpcdeploy-backend"
  echo "  systemctl reload nginx"
  exit 0
fi

install -d -m 755 "$WEB_ROOT"
rsync -av --delete "$FRONTEND_DIR/dist/" "$WEB_ROOT/"
systemctl restart hpcdeploy-backend
systemctl reload nginx

echo "HPCDeploy 已更新并重启完成"
