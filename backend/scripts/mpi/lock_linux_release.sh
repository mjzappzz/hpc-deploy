#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_ROOT="/var/backups/hpcdeploy"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/linux-release-lock-${RUN_ID}"

log() { printf '[%s] %s\n' "$1" "$2"; }
fail() { log ERROR "$1"; exit 1; }

if [[ ${EUID} -ne 0 ]]; then
    fail "必须使用 root 用户运行"
fi
if [[ ! -r /etc/os-release ]]; then
    fail "缺少 /etc/os-release，无法识别系统"
fi

# shellcheck disable=SC1091
. /etc/os-release
OS_ID="${ID,,}"
VERSION_ID="${VERSION_ID:-}"

lock_rocky_release() {
    case "$VERSION_ID" in
        "9.4") ;;
        *)
            log INFO "当前系统版本为 Rocky Linux ${VERSION_ID:-unknown}，非 9.4，无需锁定系统版本"
            return 0
            ;;
    esac
    command -v dnf >/dev/null 2>&1 || fail "未找到 dnf"
    mkdir -p "${BACKUP_DIR}"

    log INFO "备份 Rocky 官方仓库配置到 ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}/yum.repos.d"
    shopt -s nullglob
    local repo
    local rocky_repos=(/etc/yum.repos.d/rocky*.repo /etc/yum.repos.d/Rocky*.repo)
    for repo in "${rocky_repos[@]}"; do
        cp -a "$repo" "${BACKUP_DIR}/yum.repos.d/"
        rm -f "$repo"
    done
    shopt -u nullglob
    if [[ -e /etc/dnf/vars/releasever ]]; then
        cp -a /etc/dnf/vars/releasever "${BACKUP_DIR}/releasever"
    fi

    cat > /etc/yum.repos.d/rocky-9.4-hpcdeploy.repo <<'EOF'
[baseos]
name=Rocky Linux 9.4 - BaseOS - SUSTech Vault
baseurl=https://mirrors.sustech.edu.cn/rocky-vault/9.4/BaseOS/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9

[appstream]
name=Rocky Linux 9.4 - AppStream - SUSTech Vault
baseurl=https://mirrors.sustech.edu.cn/rocky-vault/9.4/AppStream/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9

[crb]
name=Rocky Linux 9.4 - CRB - SUSTech Vault
baseurl=https://mirrors.sustech.edu.cn/rocky-vault/9.4/CRB/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9
EOF
    mkdir -p /etc/dnf/vars
    printf '9.4\n' > /etc/dnf/vars/releasever

    log INFO "安装并配置 DNF versionlock；不执行全量系统升级"
    dnf install -y 'dnf-command(versionlock)'
    dnf versionlock add 'rocky-release*' 'rocky-repos*' 'rocky-gpg-keys*'
    dnf clean all
    rm -rf /var/cache/dnf
    dnf makecache

    [[ "$(tr -d '[:space:]' < /etc/dnf/vars/releasever)" == "9.4" ]] || fail "releasever 验证失败"
    dnf repolist --enabled | grep -Eq 'baseos|appstream|crb' || fail "Rocky Linux 9.4 仓库验证失败"
}

lock_ubuntu_lts() {
    if [[ "$VERSION_ID" != "22.04" && "$VERSION_ID" != "24.04" ]]; then
        fail "仅允许在已安装 Ubuntu 22.04/24.04 的服务器执行，当前版本：Ubuntu ${VERSION_ID:-unknown}"
    fi
    command -v apt-get >/dev/null 2>&1 || fail "未找到 apt-get"
    mkdir -p "${BACKUP_DIR}"

    local config=/etc/update-manager/release-upgrades
    mkdir -p "$(dirname "$config")"
    if [[ -e "$config" ]]; then
        cp -a "$config" "${BACKUP_DIR}/release-upgrades"
    fi
    if grep -q '^Prompt=' "$config" 2>/dev/null; then
        sed -i 's/^Prompt=.*/Prompt=never/' "$config"
    else
        printf '[DEFAULT]\nPrompt=never\n' >> "$config"
    fi

    log INFO "更新 Ubuntu ${VERSION_ID} 软件包索引；不执行发行版升级或全量软件包升级"
    apt-get update
    grep -qx 'Prompt=never' "$config" || fail "Ubuntu 发行版升级策略验证失败"
}

case "$OS_ID" in
    rocky) lock_rocky_release ;;
    ubuntu) lock_ubuntu_lts ;;
    *) fail "不支持的系统：ID=${OS_ID:-unknown} VERSION_ID=${VERSION_ID:-unknown}" ;;
esac

log PASS "系统版本策略配置完成"
log INFO "备份目录：${BACKUP_DIR}"
log INFO "该任务仅锁定 Rocky Linux 9.4；其他 Rocky 版本直接跳过，不执行跨版本降级"
