#!/usr/bin/env bash
set -euo pipefail

SCRIPT_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
WEB_ROOT="/var/www/hpcdeploy"
NGINX_SITE_DEST="/etc/nginx/conf.d/hpcdeploy.conf"
BACKEND_SERVICE="hpcdeploy-backend.service"
RUNTIME_DATA_PURGE=false
SECRETS_PURGE=false
FORCE=false

usage() {
  cat <<'EOF'
用法：
  sudo deploy/scripts/uninstall_hpcdeploy.sh [--purge-runtime-data] [--purge-secrets] --force

默认行为（不带 --force）：仅输出 dry-run 计划，不修改任何文件或服务。

默认卸载范围：
  - 停止并移除 hpcdeploy-backend systemd 服务
  - 移除 HPCDeploy Nginx 站点配置和 /var/www/hpcdeploy 前端静态文件
  - 保留项目源代码、SQLite、任务结果、SSH 密钥和 /etc/hpcdeploy/hpcdeploy.env

危险选项（均要求 --force）：
  --purge-runtime-data  删除 backend/data 下的运行数据及 Apptainer .sif；删除前将 SQLite
                        数据库备份到项目目录外的 ../hpcdeploy-uninstall-backups/。
  --purge-secrets       删除 backend/keys 中实际密钥及 /etc/hpcdeploy/hpcdeploy.env。

明确不做：
  - 不删除项目源代码或 Git 仓库
  - 不删除受管服务器上的任何远端目录或文件
  - 不卸载系统安装的 nginx、Python、Node.js 等共享依赖
EOF
}

die() {
  echo "错误：$*" >&2
  exit 2
}

while (($#)); do
  case "$1" in
    --purge-runtime-data) RUNTIME_DATA_PURGE=true ;;
    --purge-secrets) SECRETS_PURGE=true ;;
    --force) FORCE=true ;;
    --help|-h) usage; exit 0 ;;
    *) die "未知参数：$1（使用 --help 查看用法）" ;;
  esac
  shift
done

if { $RUNTIME_DATA_PURGE || $SECRETS_PURGE; } && ! $FORCE; then
  die "--purge-runtime-data 或 --purge-secrets 必须与 --force 一起使用"
fi

show_plan() {
  local mode="${1:-dry-run}"
  echo "HPCDeploy 卸载计划（$mode）"
  echo "项目目录：$PROJECT_ROOT"
  echo "将删除："
  echo "  - systemd 服务：$BACKEND_SERVICE"
  echo "  - Nginx 站点配置：$NGINX_SITE_DEST"
  echo "  - 已发布前端：$WEB_ROOT"
  echo "将保留："
  echo "  - 项目源代码：$PROJECT_ROOT"
  echo "  - SQLite、任务结果和运行资产"
  echo "  - SSH 密钥：$BACKEND_DIR/keys"
  echo "  - 生产环境配置：/etc/hpcdeploy/hpcdeploy.env"
  if $RUNTIME_DATA_PURGE; then
    echo "附加删除：运行数据（SQLite 先备份到项目目录外）"
  fi
  if $SECRETS_PURGE; then
    echo "附加删除：SSH 密钥和生产环境配置"
  fi
  echo "明确保留：受管服务器上的远端目录和文件"
}

if ! $FORCE; then
  show_plan
  echo "确认执行默认卸载：sudo deploy/scripts/uninstall_hpcdeploy.sh --force"
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  die "请使用 sudo 执行卸载"
fi

if ! $RUNTIME_DATA_PURGE && ! $SECRETS_PURGE; then
  show_plan "即将执行"
fi

backup_database() {
  local database_path="$BACKEND_DIR/data/hpc_control_panel.db"
  local timestamp backup_dir backup_path
  [[ -f "$database_path" ]] || return 0

  timestamp="$(date +%Y%m%d-%H%M%S)"
  backup_dir="${HPCDEPLOY_UNINSTALL_BACKUP_DIR:-$PROJECT_ROOT/../hpcdeploy-uninstall-backups}"
  backup_path="$backup_dir/hpc_control_panel_before_purge_${timestamp}.db"
  install -d -m 700 "$backup_dir"
  cp -a "$database_path" "$backup_path"
  chmod 600 "$backup_path"
  echo "SQLite 安全备份：$backup_path"
}

remove_directory_contents_except_gitkeep() {
  local directory="$1"
  [[ -d "$directory" ]] || return 0
  find "$directory" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf -- {} +
}

assert_no_active_tasks() {
  local payload active_count active_task_id
  if ! payload="$(curl --noproxy '*' --fail --silent --show-error \
    'http://127.0.0.1:8000/api/tasks?active_only=true&limit=1' 2>/dev/null)"; then
    echo "后端不可访问，无法确认活动任务；继续卸载。"
    return
  fi
  read -r active_count active_task_id < <(
    python3 -c 'import json,sys; data=json.load(sys.stdin); rows=data.get("items") or []; print(int(data.get("total") or 0), rows[0].get("task_id", "-") if rows else "-")' \
      <<< "$payload"
  )
  if (( active_count > 0 )); then
    echo "检测到活动任务，拒绝卸载：count=$active_count task_id=$active_task_id" >&2
    exit 1
  fi
}

assert_no_active_tasks

if systemctl list-unit-files "$BACKEND_SERVICE" >/dev/null 2>&1; then
  systemctl disable --now "$BACKEND_SERVICE" || true
fi
rm -f "/etc/systemd/system/$BACKEND_SERVICE"
systemctl daemon-reload

rm -f "$NGINX_SITE_DEST"
rm -rf -- "$WEB_ROOT"
if command -v nginx >/dev/null 2>&1; then
  nginx -t
  systemctl reload nginx 2>/dev/null || true
fi

if $RUNTIME_DATA_PURGE; then
  backup_database
  remove_directory_contents_except_gitkeep "$BACKEND_DIR/data"
  find "$BACKEND_DIR/apptainer" -mindepth 1 -maxdepth 1 -type f -name '*.sif' -delete 2>/dev/null || true
fi

if $SECRETS_PURGE; then
  remove_directory_contents_except_gitkeep "$BACKEND_DIR/keys"
  rm -f /etc/hpcdeploy/hpcdeploy.env
fi

echo "HPCDeploy 卸载完成"
echo "卸载脚本版本：$SCRIPT_VERSION"
echo "未删除项目源代码或任何受管服务器远端目录。"
