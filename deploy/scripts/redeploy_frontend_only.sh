#!/usr/bin/env bash
set -euo pipefail

# Publish only immutable frontend assets. This script intentionally never
# restarts the backend: it is safe to run while remote tasks are active.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common_runtime.sh"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
WEB_ROOT="/var/www/hpcdeploy"
RELEASE_ROOT="/var/www/.hpcdeploy-releases"
RELEASE_ID="$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="$RELEASE_ROOT/$RELEASE_ID"
CURRENT_LINK="$RELEASE_ROOT/current"
TEMP_LINK="$RELEASE_ROOT/.current-$RELEASE_ID"

run_as_service_user() {
  if [[ "$SERVICE_USER" == "root" ]]; then
    env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  else
    sudo -H -u "$SERVICE_USER" env "PATH=$NODE_BIN_DIR:$PATH" "$@"
  fi
}

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 执行前端独立发布："
  echo "  sudo deploy/scripts/redeploy_frontend_only.sh"
  echo "该操作不会重启 hpcdeploy-backend，也不会停止活动任务。"
  exit 0
fi

NODE_BIN_DIR="$(resolve_service_node_bin "$SERVICE_USER")"
cd "$FRONTEND_DIR"
if [[ -f package-lock.json ]]; then
  run_as_service_user npm ci
else
  run_as_service_user npm install
fi
run_as_service_user npm run build
test -f "$FRONTEND_DIR/dist/index.html"
nginx -t

install -d -m 755 "$RELEASE_ROOT"
install -d -m 755 "$RELEASE_DIR"
cp -a "$FRONTEND_DIR/dist/." "$RELEASE_DIR/"
find "$RELEASE_DIR" -type d -exec chmod 755 {} +
find "$RELEASE_DIR" -type f -exec chmod 644 {} +

# The first independent publish converts the mutable web root into an atomic
# symlink while retaining the old files as a rollback release.
if [[ -d "$WEB_ROOT" && ! -L "$WEB_ROOT" ]]; then
  legacy_release="$RELEASE_ROOT/legacy-$(date +%Y%m%d-%H%M%S)"
  mv "$WEB_ROOT" "$legacy_release"
  ln -s "$legacy_release" "$CURRENT_LINK"
fi
ln -s "$RELEASE_DIR" "$TEMP_LINK"
mv -Tf "$TEMP_LINK" "$CURRENT_LINK"
ln -sfn "$CURRENT_LINK" "$WEB_ROOT"

echo "前端静态资源已原子发布：$RELEASE_ID"
echo "后端未重启；如需回滚，将 $CURRENT_LINK 指向上一发布目录后执行 nginx -t。"
