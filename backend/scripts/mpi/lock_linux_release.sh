#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_VERSION="1.7.6"
BACKUP_ROOT="/var/backups/hpcdeploy"
RUN_ID="$(date +%Y%m%d-%H%M%S-%N)-${BASHPID}"
BACKUP_DIR="${BACKUP_ROOT}/linux-release-lock-${RUN_ID}"
ROCKY_MUTATION_STARTED=0
ROCKY_RELEASEVER_EXISTED=0
VERSIONLOCK_LIST="/etc/dnf/plugins/versionlock.list"
VERSIONLOCK_LIST_EXISTED=0
KERNEL_LOCK_SPECS=()
KERNEL_LOCK_CHECKS=()
UBUNTU_MUTATION_STARTED=0
UBUNTU_RELEASE_CONFIG_EXISTED=0
UBUNTU_KERNEL_HOLD_PACKAGES=()
UBUNTU_NEW_KERNEL_HOLDS=()
APT_LOCK_MAX_WAIT_SECONDS=900
APT_LOCK_POLL_SECONDS=5
APT_STALL_MAX_SECONDS=10
APT_MIN_DOWNLOAD_BYTES_PER_SECOND=524288
APT_LOCK_FILES=(
    /var/lib/dpkg/lock-frontend
    /var/lib/dpkg/lock
    /var/lib/apt/lists/lock
    /var/cache/apt/archives/lock
)

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

write_rocky_repo_config() {
    local root="$1"
    local target="$2"
    cat > "$target" <<EOF
[baseos]
name=Rocky Linux ${VERSION_ID} - BaseOS - HPCDeploy Locked
baseurl=${root}/BaseOS/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9

[appstream]
name=Rocky Linux ${VERSION_ID} - AppStream - HPCDeploy Locked
baseurl=${root}/AppStream/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9

[crb]
name=Rocky Linux ${VERSION_ID} - CRB - HPCDeploy Locked
baseurl=${root}/CRB/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9
EOF
}

write_epel_repo_config() {
    local target="$1"
    cat > "$target" <<'EOF'
[epel]
name=Extra Packages for Enterprise Linux 9 - $basearch
baseurl=https://mirrors.aliyun.com/epel/9/Everything/$basearch/
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-9
skip_if_unavailable=0
EOF
}

probe_rocky_repo_root() {
    local root="$1"
    local probe_root
    local probe_status
    probe_root="$(mktemp -d)"
    write_rocky_repo_config "$root" "${probe_root}/rocky.repo"
    write_epel_repo_config "${probe_root}/epel.repo"

    if LC_ALL=C timeout --signal=TERM --kill-after=10s 90s dnf -q \
        "--setopt=reposdir=${probe_root}" \
        "--setopt=cachedir=${probe_root}/cache" \
        "--setopt=persistdir=${probe_root}/persist" \
        "--setopt=timeout=20" \
        "--setopt=retries=2" \
        --disablerepo='*' \
        --enablerepo=baseos \
        --enablerepo=appstream \
        --enablerepo=crb \
        --enablerepo=epel \
        makecache --refresh >/dev/null; then
        rm -rf "$probe_root"
        return 0
    else
        probe_status=$?
    fi
    if (( probe_status == 124 || probe_status == 137 )); then
        log WARN "仓库预检超过 90 秒，已终止 DNF 并切换候选源：${root}" >&2
    fi
    rm -rf "$probe_root"
    return 1
}

select_rocky_repo_root() {
    local candidates=(
        "https://mirrors.sustech.edu.cn/rocky-vault/${VERSION_ID}"
        "https://download.rockylinux.org/pub/rocky/${VERSION_ID}"
        "https://download.rockylinux.org/vault/rocky/${VERSION_ID}"
    )
    local candidate
    for candidate in "${candidates[@]}"; do
        log INFO "预检 Rocky Linux ${VERSION_ID} 仓库：${candidate}" >&2
        if probe_rocky_repo_root "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
        log WARN "仓库不可用，尝试下一候选源：${candidate}" >&2
    done
    return 1
}

append_kernel_lock_spec() {
    local query="$1"
    local spec
    local check
    spec="$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' "$query")" || return 1
    check="$(rpm -q --qf '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}' "$query")" || return 1
    KERNEL_LOCK_SPECS+=("$spec")
    KERNEL_LOCK_CHECKS+=("$check")
}

collect_running_kernel_lock_specs() {
    local running_kernel="$1"
    local package_name
    local query
    local header_query

    rpm -q "kernel-core-${running_kernel}" >/dev/null 2>&1 \
        || fail "当前运行内核缺少对应 kernel-core RPM：${running_kernel}"

    for package_name in \
        kernel \
        kernel-core \
        kernel-modules \
        kernel-modules-core \
        kernel-modules-extra \
        kernel-devel; do
        query="${package_name}-${running_kernel}"
        if rpm -q "$query" >/dev/null 2>&1; then
            append_kernel_lock_spec "$query" \
                || fail "无法读取内核包版本：${query}"
        fi
    done

    if rpm -q kernel-devel >/dev/null 2>&1 \
        && ! rpm -q "kernel-devel-${running_kernel}" >/dev/null 2>&1; then
        log WARN "已安装 kernel-devel，但与当前运行内核 ${running_kernel} 不匹配；不自动安装或切换版本"
    fi

    if rpm -q kernel-headers >/dev/null 2>&1; then
        while IFS= read -r header_query; do
            [[ -n "$header_query" ]] || continue
            append_kernel_lock_spec "$header_query" \
                || fail "无法读取内核头文件包版本：${header_query}"
        done < <(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-headers)
    fi

    (( ${#KERNEL_LOCK_SPECS[@]} > 0 )) \
        || fail "未识别到可锁定的当前内核 RPM"
}

verify_kernel_versionlocks() {
    local versionlock_output="$1"
    local check
    for check in "${KERNEL_LOCK_CHECKS[@]}"; do
        grep -Fq "$check" <<< "$versionlock_output" \
            || fail "内核 versionlock 验证失败：${check}"
    done
}

ubuntu_package_is_installed() {
    local status
    status="$(dpkg-query -W -f='${db:Status-Abbrev}' "$1" 2>/dev/null)" || return 1
    [[ "$status" == "ii " || "$status" == "hi " ]]
}

append_ubuntu_kernel_hold_package() {
    local package_name="$1"
    local existing
    ubuntu_package_is_installed "$package_name" || return 0
    for existing in "${UBUNTU_KERNEL_HOLD_PACKAGES[@]}"; do
        [[ "$existing" == "$package_name" ]] && return 0
    done
    UBUNTU_KERNEL_HOLD_PACKAGES+=("$package_name")
}

collect_ubuntu_kernel_hold_packages() {
    local running_kernel="$1"
    local kernel_abi="${running_kernel%-*}"
    local package_name

    for package_name in \
        "linux-image-${running_kernel}" \
        "linux-image-unsigned-${running_kernel}" \
        "linux-modules-${running_kernel}" \
        "linux-modules-extra-${running_kernel}" \
        "linux-headers-${running_kernel}" \
        "linux-headers-${kernel_abi}"; do
        append_ubuntu_kernel_hold_package "$package_name"
    done

    while IFS= read -r package_name; do
        [[ "$package_name" =~ ^linux-(generic|image-generic|headers-generic|virtual|image-virtual|headers-virtual|lowlatency|image-lowlatency|headers-lowlatency)(-hwe-[0-9]+\.[0-9]+)?$ \
            || "$package_name" =~ ^linux-(oem|image-oem|headers-oem)-[0-9]+\.[0-9]+ ]] \
            || continue
        append_ubuntu_kernel_hold_package "$package_name"
    done < <(dpkg-query -W -f='${binary:Package}\n' 'linux-*' 2>/dev/null | sed 's/:.*$//' | sort -u)

    (( ${#UBUNTU_KERNEL_HOLD_PACKAGES[@]} > 0 )) \
        || fail "未识别到当前运行内核对应的已安装 DEB 包：${running_kernel}"
    ubuntu_package_is_installed "linux-image-${running_kernel}" \
        || ubuntu_package_is_installed "linux-image-unsigned-${running_kernel}" \
        || fail "当前运行内核缺少对应 linux-image DEB：${running_kernel}"
}

verify_ubuntu_kernel_holds() {
    local held_packages
    local package_name
    held_packages="$(apt-mark showhold)"
    for package_name in "${UBUNTU_KERNEL_HOLD_PACKAGES[@]}"; do
        grep -Fxq "$package_name" <<< "$held_packages" \
            || fail "Ubuntu 内核 hold 验证失败：${package_name}"
    done
}

apt_dpkg_lock_holders() {
    if command -v fuser >/dev/null 2>&1; then
        fuser "${APT_LOCK_FILES[@]}" 2>/dev/null || true
        return 0
    fi

    command -v lslocks >/dev/null 2>&1 \
        || fail "未找到 fuser 或 lslocks，无法安全确认 apt/dpkg 锁状态"

    local lock_file
    local pid
    local path
    local lock_pids=()

    while read -r pid path; do
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        for lock_file in "${APT_LOCK_FILES[@]}"; do
            [[ "$path" == "$lock_file" ]] || continue
            lock_pids+=("$pid")
            break
        done
    done < <(lslocks -n -o PID,PATH 2>/dev/null || true)

    (( ${#lock_pids[@]} > 0 )) || return 0
    printf '%s\n' "${lock_pids[@]}" | sort -u | tr '\n' ' '
}

wait_for_apt_dpkg_unlock() {
    local operation="$1"
    local elapsed=0
    local stalled_seconds=0
    local recovered_automatic_update=0
    local holders
    local download_bytes
    local previous_download_bytes=""
    local cpu_times
    local previous_cpu_times=""
    local minimum_download_bytes
    local downloaded_bytes

    while true; do
        holders="$(apt_dpkg_lock_holders)"
        [[ -z "${holders//[[:space:]]/}" ]] && return 0
        download_bytes="$(apt_update_download_bytes)"
        cpu_times="$(apt_update_cpu_times "$holders")"
        if [[ -n "$previous_download_bytes" ]]; then
            minimum_download_bytes=$((APT_MIN_DOWNLOAD_BYTES_PER_SECOND * APT_LOCK_POLL_SECONDS))
            downloaded_bytes=$((download_bytes - previous_download_bytes))
            if [[ "$cpu_times" == "$previous_cpu_times" && "$downloaded_bytes" -lt "$minimum_download_bytes" ]]; then
                ((stalled_seconds += APT_LOCK_POLL_SECONDS))
            else
                stalled_seconds=0
            fi
        fi
        previous_download_bytes="$download_bytes"
        previous_cpu_times="$cpu_times"
        if (( stalled_seconds >= APT_STALL_MAX_SECONDS )); then
            if (( recovered_automatic_update == 0 )) && is_stalled_automatic_apt_update "$holders"; then
                recover_stalled_automatic_apt_update "$holders"
                recovered_automatic_update=1
                stalled_seconds=0
                previous_download_bytes=""
                previous_cpu_times=""
                continue
            fi
            log WARN "${operation} 的 apt/dpkg 锁下载速率低于 $((APT_MIN_DOWNLOAD_BYTES_PER_SECOND / 1024))KiB/s 且无 CPU 配置进展已达 ${stalled_seconds} 秒；仅自动更新允许恢复，人工 apt/dpkg 或 cloud-init 继续等待"
        fi
        if (( elapsed >= APT_LOCK_MAX_WAIT_SECONDS )); then
            fail "apt/dpkg 锁持续占用超过 ${APT_LOCK_MAX_WAIT_SECONDS} 秒，未删除锁文件或终止进程；占用 PID：${holders}"
        fi
        log WARN "${operation} 等待 apt/dpkg 锁释放（已等待 ${elapsed} 秒；占用 PID：${holders}）"
        sleep "$APT_LOCK_POLL_SECONDS"
        ((elapsed += APT_LOCK_POLL_SECONDS))
    done
}

apt_update_download_bytes() {
    find /var/cache/apt/archives/partial -maxdepth 1 -type f -printf '%s\n' 2>/dev/null \
        | awk '{total += $1} END {print total + 0}'
}

apt_update_cpu_times() {
    local holders="$1"
    local pid
    for pid in $holders; do
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        ps -o cputime= -p "$pid" 2>/dev/null | tr -d '[:space:]'
    done
}

is_stalled_automatic_apt_update() {
    local holders="$1"
    local pid
    local holder_command
    local automatic_holder_count=0

    for pid in $holders; do
        [[ "$pid" =~ ^[0-9]+$ ]] || return 1
        holder_command="$(ps -o args= -p "$pid" 2>/dev/null || true)"
        [[ "$holder_command" == *"/usr/bin/unattended-upgrade"* ]] || return 1
        grep -Fqx '0::/system.slice/apt-daily-upgrade.service' "/proc/${pid}/cgroup" 2>/dev/null || return 1
        ((automatic_holder_count += 1))
    done
    (( automatic_holder_count > 0 ))
}

recover_stalled_automatic_apt_update() {
    local holders="$1"
    local attempt
    local remaining_holders

    log WARN "检测到 apt-daily-upgrade / unattended-upgrade 连续 ${APT_STALL_MAX_SECONDS} 秒下载速率过低且无 CPU 配置进展；开始受控恢复"
    log WARN "仅恢复系统自动更新；不终止人工 apt/dpkg 或 cloud-init"
    systemctl stop --no-block apt-daily-upgrade.service \
        || fail "无法停止无进展的 apt-daily-upgrade.service；占用 PID：${holders}"
    systemctl kill --kill-who=all --signal=SIGTERM apt-daily-upgrade.service \
        || fail "无法向 apt-daily-upgrade 的自动更新进程发送 SIGTERM；占用 PID：${holders}"
    for ((attempt = 1; attempt <= 12; attempt += 1)); do
        remaining_holders="$(apt_dpkg_lock_holders)"
        [[ -z "${remaining_holders//[[:space:]]/}" ]] && break
        sleep "$APT_LOCK_POLL_SECONDS"
    done
    [[ -z "${remaining_holders//[[:space:]]/}" ]] \
        || fail "已停止 apt-daily-upgrade，但 apt/dpkg 锁仍被占用；未强制终止进程，PID：${remaining_holders}"
    log INFO "自动更新已停止且锁已释放，执行 dpkg 一致性恢复"
    DEBIAN_FRONTEND=noninteractive dpkg --configure -a \
        || fail "dpkg 一致性恢复失败；请人工检查后重试"
    log PASS "无进展的系统自动更新已安全停止，dpkg 状态恢复完成；继续执行系统版本锁定"
}

repo_file_has_managed_id() {
    grep -Eq '^[[:space:]]*\[(baseos|appstream|crb|epel)\][[:space:]]*$' "$1"
}

remove_managed_repo_files() {
    local repo
    local stripped
    shopt -s nullglob
    for repo in /etc/yum.repos.d/*.repo; do
        repo_file_has_managed_id "$repo" || continue
        stripped="$(mktemp "${repo}.hpcdeploy.XXXXXX")"
        awk '
            /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
                header = $0
                gsub(/[[:space:]]/, "", header)
                skip = (header ~ /^\[(baseos|appstream|crb|epel)\]$/)
            }
            !skip { print }
        ' "$repo" > "$stripped"
        if grep -Eq '^[[:space:]]*\[[^]]+\][[:space:]]*$' "$stripped"; then
            chmod --reference="$repo" "$stripped"
            mv -f "$stripped" "$repo"
        else
            rm -f "$stripped" "$repo"
        fi
    done
    shopt -u nullglob
}

verify_repo_backup_restored() {
    local repo
    local current
    shopt -s nullglob
    for repo in "${BACKUP_DIR}"/yum.repos.d/*.repo; do
        cmp -s "$repo" "/etc/yum.repos.d/$(basename "$repo")" || {
            shopt -u nullglob
            return 1
        }
    done
    for current in /etc/yum.repos.d/*.repo; do
        [[ -f "${BACKUP_DIR}/yum.repos.d/$(basename "$current")" ]] || {
            shopt -u nullglob
            return 1
        }
    done
    shopt -u nullglob
}

rollback_rocky_config() {
    (( ROCKY_MUTATION_STARTED == 1 )) || return 0
    ROCKY_MUTATION_STARTED=0
    set +e
    local rollback_failed=0
    log WARN "锁定失败，开始恢复执行前仓库配置"
    find /etc/yum.repos.d -maxdepth 1 -type f -name '*.repo' -delete || rollback_failed=1
    if [[ -d "${BACKUP_DIR}/yum.repos.d" ]]; then
        cp -a "${BACKUP_DIR}/yum.repos.d/." /etc/yum.repos.d/ || rollback_failed=1
        verify_repo_backup_restored || rollback_failed=1
    fi
    if (( ROCKY_RELEASEVER_EXISTED == 1 )); then
        cp -a "${BACKUP_DIR}/releasever" /etc/dnf/vars/releasever || rollback_failed=1
        cmp -s "${BACKUP_DIR}/releasever" /etc/dnf/vars/releasever || rollback_failed=1
    else
        rm -f /etc/dnf/vars/releasever || rollback_failed=1
        [[ ! -e /etc/dnf/vars/releasever ]] || rollback_failed=1
    fi
    if (( VERSIONLOCK_LIST_EXISTED == 1 )); then
        mkdir -p "$(dirname "$VERSIONLOCK_LIST")" || rollback_failed=1
        cp -a "${BACKUP_DIR}/versionlock.list" "$VERSIONLOCK_LIST" || rollback_failed=1
        cmp -s "${BACKUP_DIR}/versionlock.list" "$VERSIONLOCK_LIST" || rollback_failed=1
    else
        rm -f "$VERSIONLOCK_LIST" || rollback_failed=1
        [[ ! -e "$VERSIONLOCK_LIST" ]] || rollback_failed=1
    fi
    if (( rollback_failed != 0 )); then
        log ERROR "自动回滚未完整通过校验；请使用备份目录人工恢复：${BACKUP_DIR}"
        return 1
    fi
    log WARN "仓库配置已从 ${BACKUP_DIR} 回滚并通过文件校验"
}

rollback_ubuntu_config() {
    (( UBUNTU_MUTATION_STARTED == 1 )) || return 0
    UBUNTU_MUTATION_STARTED=0
    set +e
    local rollback_failed=0
    local package_name
    local config=/etc/update-manager/release-upgrades
    log WARN "锁定失败，开始恢复 Ubuntu 发行版与内核 hold 策略"
    for package_name in "${UBUNTU_NEW_KERNEL_HOLDS[@]}"; do
        apt-mark unhold "$package_name" >/dev/null || rollback_failed=1
    done
    if (( UBUNTU_RELEASE_CONFIG_EXISTED == 1 )); then
        cp -a "${BACKUP_DIR}/release-upgrades" "$config" || rollback_failed=1
        cmp -s "${BACKUP_DIR}/release-upgrades" "$config" || rollback_failed=1
    else
        rm -f "$config" || rollback_failed=1
        [[ ! -e "$config" ]] || rollback_failed=1
    fi
    if (( rollback_failed != 0 )); then
        log ERROR "Ubuntu 自动回滚未完整通过校验；请使用备份目录人工恢复：${BACKUP_DIR}"
        return 1
    fi
    log WARN "Ubuntu 发行版与内核 hold 策略已回滚"
}

handle_script_exit() {
    local status="$?"
    if (( status != 0 )); then
        if ! rollback_rocky_config || ! rollback_ubuntu_config; then
            status=2
        fi
    fi
    exit "$status"
}

trap handle_script_exit EXIT

lock_rocky_release() {
    [[ "$VERSION_ID" =~ ^9\.[0-9]+$ ]] \
        || fail "仅支持锁定 Rocky Linux 9.x 当前小版本，当前版本：${VERSION_ID:-unknown}"
    [[ "$(uname -m)" == "x86_64" ]] \
        || fail "当前脚本仅支持 x86_64，检测到架构：$(uname -m)"
    command -v dnf >/dev/null 2>&1 || fail "未找到 dnf"
    command -v rpm >/dev/null 2>&1 || fail "未找到 rpm"
    command -v timeout >/dev/null 2>&1 || fail "未找到 timeout（coreutils）"

    local running_kernel
    running_kernel="$(uname -r)"
    collect_running_kernel_lock_specs "$running_kernel"

    local repo_root
    repo_root="$(select_rocky_repo_root)" \
        || fail "Rocky Linux ${VERSION_ID} 的 BaseOS/AppStream/CRB 固定版本仓库均不可用，未修改系统配置"

    local rocky_repo_tmp
    local epel_repo_tmp
    rocky_repo_tmp="$(mktemp)"
    epel_repo_tmp="$(mktemp)"
    write_rocky_repo_config "$repo_root" "$rocky_repo_tmp"
    write_epel_repo_config "$epel_repo_tmp"

    mkdir -p "${BACKUP_ROOT}"
    mkdir "${BACKUP_DIR}" \
        || fail "无法排他创建备份目录，未修改系统配置：${BACKUP_DIR}"

    log INFO "备份全部 DNF 仓库配置到 ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}/yum.repos.d"
    local repo
    shopt -s nullglob
    for repo in /etc/yum.repos.d/*.repo; do
        cp -a "$repo" "${BACKUP_DIR}/yum.repos.d/"
    done
    shopt -u nullglob
    if [[ -e /etc/dnf/vars/releasever ]]; then
        ROCKY_RELEASEVER_EXISTED=1
        cp -a /etc/dnf/vars/releasever "${BACKUP_DIR}/releasever"
    fi
    if [[ -e "$VERSIONLOCK_LIST" ]]; then
        VERSIONLOCK_LIST_EXISTED=1
        cp -a "$VERSIONLOCK_LIST" "${BACKUP_DIR}/versionlock.list"
    fi

    ROCKY_MUTATION_STARTED=1
    remove_managed_repo_files
    install -m 0644 "$rocky_repo_tmp" "/etc/yum.repos.d/rocky-${VERSION_ID}-hpcdeploy.repo"
    install -m 0644 "$epel_repo_tmp" /etc/yum.repos.d/epel.repo
    rm -f "$rocky_repo_tmp" "$epel_repo_tmp"
    mkdir -p /etc/dnf/vars
    printf '%s\n' "$VERSION_ID" > /etc/dnf/vars/releasever

    local dnf_core_args=(
        "--disablerepo=*"
        "--enablerepo=baseos"
        "--enablerepo=appstream"
        "--enablerepo=crb"
        "--setopt=timeout=20"
        "--setopt=retries=2"
    )

    dnf "${dnf_core_args[@]}" "--enablerepo=epel" makecache --refresh

    local enabled_repo_ids
    enabled_repo_ids="$(LC_ALL=C dnf -q repolist --enabled | awk '{print $1}')"
    local required_repo
    local repo_id_count
    for required_repo in baseos appstream crb epel; do
        grep -Fxq "$required_repo" <<< "$enabled_repo_ids" \
            || fail "锁定后缺少已启用仓库：${required_repo}"
        repo_id_count="$(
            awk -v target="[${required_repo}]" '
                {
                    line = $0
                    gsub(/[[:space:]]/, "", line)
                    if (line == target) count++
                }
                END { print count + 0 }
            ' /etc/yum.repos.d/*.repo
        )"
        [[ "$repo_id_count" == "1" ]] \
            || fail "锁定后仓库 ID ${required_repo} 定义数量异常：${repo_id_count}"
    done
    grep -Fqx "baseurl=${repo_root}/BaseOS/x86_64/os/" "/etc/yum.repos.d/rocky-${VERSION_ID}-hpcdeploy.repo" \
        || fail "BaseOS 固定版本地址验证失败"
    grep -Fqx "baseurl=${repo_root}/AppStream/x86_64/os/" "/etc/yum.repos.d/rocky-${VERSION_ID}-hpcdeploy.repo" \
        || fail "AppStream 固定版本地址验证失败"
    grep -Fqx "baseurl=${repo_root}/CRB/x86_64/os/" "/etc/yum.repos.d/rocky-${VERSION_ID}-hpcdeploy.repo" \
        || fail "CRB 固定版本地址验证失败"

    log INFO "安装并配置 DNF versionlock；不执行全量系统升级"
    if dnf "${dnf_core_args[@]}" versionlock list >/dev/null 2>&1; then
        log INFO "DNF versionlock 已安装，跳过重复安装"
    else
        dnf "${dnf_core_args[@]}" install -y 'dnf-command(versionlock)'
    fi
    dnf "${dnf_core_args[@]}" versionlock add 'rocky-release*' 'rocky-repos*' 'rocky-gpg-keys*'
    dnf "${dnf_core_args[@]}" versionlock add "${KERNEL_LOCK_SPECS[@]}"

    [[ "$(tr -d '[:space:]' < /etc/dnf/vars/releasever)" == "$VERSION_ID" ]] || fail "releasever 验证失败"
    local versionlock_output
    versionlock_output="$(dnf "${dnf_core_args[@]}" versionlock list)"
    verify_kernel_versionlocks "$versionlock_output"

    log INFO "检测版本：Rocky Linux ${VERSION_ID}"
    log INFO "锁定版本：${VERSION_ID}"
    log INFO "仓库来源：${repo_root}"
    log INFO "当前运行内核：${running_kernel}"
    log INFO "内核锁定：已完成（${#KERNEL_LOCK_SPECS[@]} 个已安装包）"
    log INFO "内核安全更新：需在维护窗口手动解锁、升级并重新验证驱动"
    log INFO "跨版本升级：禁止"
    log INFO "全量系统升级：未执行"
    ROCKY_MUTATION_STARTED=0
}

lock_ubuntu_lts() {
    if [[ "$VERSION_ID" != "22.04" && "$VERSION_ID" != "24.04" ]]; then
        fail "仅允许在已安装 Ubuntu 22.04/24.04 的服务器执行，当前版本：Ubuntu ${VERSION_ID:-unknown}"
    fi
    command -v apt-get >/dev/null 2>&1 || fail "未找到 apt-get"
    command -v apt-mark >/dev/null 2>&1 || fail "未找到 apt-mark"
    command -v dpkg-query >/dev/null 2>&1 || fail "未找到 dpkg-query"
    if ! command -v fuser >/dev/null 2>&1 && ! command -v lslocks >/dev/null 2>&1; then
        fail "未找到 fuser 或 lslocks，无法安全确认 apt/dpkg 锁状态"
    fi

    local running_kernel
    running_kernel="$(uname -r)"
    collect_ubuntu_kernel_hold_packages "$running_kernel"
    wait_for_apt_dpkg_unlock "读取 Ubuntu hold 策略前"
    mkdir -p "${BACKUP_DIR}"
    apt-mark showhold > "${BACKUP_DIR}/apt-mark-showhold.before"

    local config=/etc/update-manager/release-upgrades
    mkdir -p "$(dirname "$config")"
    if [[ -e "$config" ]]; then
        UBUNTU_RELEASE_CONFIG_EXISTED=1
        cp -a "$config" "${BACKUP_DIR}/release-upgrades"
    fi
    local held_packages_before
    local package_name
    held_packages_before="$(<"${BACKUP_DIR}/apt-mark-showhold.before")"
    for package_name in "${UBUNTU_KERNEL_HOLD_PACKAGES[@]}"; do
        if ! grep -Fxq "$package_name" <<< "$held_packages_before"; then
            UBUNTU_NEW_KERNEL_HOLDS+=("$package_name")
        fi
    done

    UBUNTU_MUTATION_STARTED=1
    if grep -q '^Prompt=' "$config" 2>/dev/null; then
        sed -i 's/^Prompt=.*/Prompt=never/' "$config"
    else
        printf '[DEFAULT]\nPrompt=never\n' >> "$config"
    fi

    log INFO "更新 Ubuntu ${VERSION_ID} 软件包索引；不执行发行版升级或全量软件包升级"
    wait_for_apt_dpkg_unlock "更新 Ubuntu 软件包索引前"
    apt-get update
    wait_for_apt_dpkg_unlock "写入 Ubuntu 内核 hold 前"
    apt-mark hold "${UBUNTU_KERNEL_HOLD_PACKAGES[@]}"
    grep -qx 'Prompt=never' "$config" || fail "Ubuntu 发行版升级策略验证失败"
    verify_ubuntu_kernel_holds
    log INFO "当前运行内核：${running_kernel}"
    log INFO "内核锁定：已完成（${#UBUNTU_KERNEL_HOLD_PACKAGES[@]} 个已安装包）"
    log INFO "内核安全更新：需在维护窗口手动解除 hold、升级并重新验证驱动"
    UBUNTU_MUTATION_STARTED=0
}

case "$OS_ID" in
    rocky) lock_rocky_release ;;
    ubuntu) lock_ubuntu_lts ;;
    *) fail "不支持的系统：ID=${OS_ID:-unknown} VERSION_ID=${VERSION_ID:-unknown}" ;;
esac

log INFO "脚本版本：${SCRIPT_VERSION}"
log PASS "系统版本策略配置完成"
log INFO "备份目录：${BACKUP_DIR}"
if [[ "$OS_ID" == "rocky" ]]; then
    log INFO "Rocky Linux 仅锁定执行前检测到的当前 9.x 小版本，不执行跨版本升级或降级"
fi
