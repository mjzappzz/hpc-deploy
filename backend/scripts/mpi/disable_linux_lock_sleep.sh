#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_ROOT="/var/backups/hpcdeploy"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/disable-lock-sleep-${RUN_ID}"

log() { printf '[%s] %s\n' "$1" "$2"; }
fail() { log ERROR "$1"; exit 1; }
backup_file() {
    local path="$1"
    if [[ -e "$path" ]]; then
        mkdir -p "${BACKUP_DIR}$(dirname "$path")"
        cp -a "$path" "${BACKUP_DIR}${path}"
    fi
}

if [[ ${EUID} -ne 0 ]]; then
    fail "必须使用 root 用户运行"
fi
if [[ ! -r /etc/os-release ]]; then
    fail "缺少 /etc/os-release，无法识别系统"
fi
# shellcheck disable=SC1091
. /etc/os-release
case "${ID,,}" in
    rocky|rhel|almalinux|ubuntu) ;;
    *) fail "不支持的系统：ID=${ID:-unknown}" ;;
esac
command -v systemctl >/dev/null 2>&1 || fail "未找到 systemctl"
mkdir -p "$BACKUP_DIR"

log INFO "禁用 systemd 睡眠、挂起和休眠目标"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

LOGIND_DROPIN=/etc/systemd/logind.conf.d/99-hpcdeploy-disable-sleep.conf
backup_file "$LOGIND_DROPIN"
mkdir -p "$(dirname "$LOGIND_DROPIN")"
cat > "$LOGIND_DROPIN" <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
IdleAction=ignore
IdleActionSec=0
EOF
log INFO "logind 配置已写入；为避免中断会话，本任务不立即重启 systemd-logind"

DCONF_DEFAULT=/etc/dconf/db/local.d/00-hpcdeploy-disable-lock
DCONF_LOCKS=/etc/dconf/db/local.d/locks/00-hpcdeploy-disable-lock
backup_file "$DCONF_DEFAULT"
backup_file "$DCONF_LOCKS"
mkdir -p "$(dirname "$DCONF_LOCKS")"
cat > "$DCONF_DEFAULT" <<'EOF'
[org/gnome/desktop/session]
idle-delay=uint32 0

[org/gnome/desktop/screensaver]
lock-enabled=false
idle-activation-enabled=false

[org/gnome/settings-daemon/plugins/power]
sleep-inactive-ac-type='nothing'
sleep-inactive-battery-type='nothing'
sleep-inactive-ac-timeout=0
sleep-inactive-battery-timeout=0
EOF
cat > "$DCONF_LOCKS" <<'EOF'
/org/gnome/desktop/session/idle-delay
/org/gnome/desktop/screensaver/lock-enabled
/org/gnome/desktop/screensaver/idle-activation-enabled
/org/gnome/settings-daemon/plugins/power/sleep-inactive-ac-type
/org/gnome/settings-daemon/plugins/power/sleep-inactive-battery-type
/org/gnome/settings-daemon/plugins/power/sleep-inactive-ac-timeout
/org/gnome/settings-daemon/plugins/power/sleep-inactive-battery-timeout
EOF
if command -v dconf >/dev/null 2>&1; then
    dconf update
else
    log SKIP "未安装 dconf，跳过 GNOME 系统策略编译"
fi

KDE_CONFIG=/etc/xdg/kscreenlockerrc
backup_file "$KDE_CONFIG"
mkdir -p "$(dirname "$KDE_CONFIG")"
cat > "$KDE_CONFIG" <<'EOF'
[Daemon]
Autolock=false
LockOnResume=false
Timeout=0
EOF

AUTOSTART=/etc/xdg/autostart/hpcdeploy-disable-screen-blank.desktop
backup_file "$AUTOSTART"
mkdir -p "$(dirname "$AUTOSTART")"
cat > "$AUTOSTART" <<'EOF'
[Desktop Entry]
Type=Application
Name=HPCDeploy Disable Screen Blank
Exec=sh -c 'command -v xset >/dev/null 2>&1 && xset s off && xset -dpms && xset s noblank || true'
OnlyShowIn=GNOME;KDE;XFCE;
X-GNOME-Autostart-enabled=true
EOF

for target in sleep.target suspend.target hibernate.target hybrid-sleep.target; do
    [[ "$(systemctl is-enabled "$target" 2>/dev/null || true)" == "masked" ]] || fail "${target} 未成功 mask"
done
grep -qx 'IdleAction=ignore' "$LOGIND_DROPIN" || fail "logind 配置验证失败"
grep -qx 'lock-enabled=false' "$DCONF_DEFAULT" || fail "GNOME 锁屏配置验证失败"

log PASS "Linux 自动锁屏、待机和休眠策略配置完成"
log INFO "备份目录：${BACKUP_DIR}"
log INFO "桌面策略在用户重新登录后生效；logind 策略建议维护窗口重启系统后生效"
