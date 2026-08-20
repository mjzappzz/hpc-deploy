#!/usr/bin/env bash

set -u
set -o pipefail

SCRIPT_VERSION="2026.08.20.1"

DNF_MINRATE="${HPCDEPLOY_DNF_MINRATE:-51200}"
DNF_TIMEOUT="${HPCDEPLOY_DNF_TIMEOUT:-30}"
DNF_RETRIES="${HPCDEPLOY_DNF_RETRIES:-2}"
DNF_INSTALL_ATTEMPTS="${HPCDEPLOY_DNF_INSTALL_ATTEMPTS:-3}"

# ============================================================
# GPU 多卡稳定性压力测试报告脚本
#
# 用法：
#   bash gpu_stress_report.sh 14400
#   bash gpu_stress_report.sh 14400 2
#
# 参数：
#   $1 = 压测秒数，默认 43200
#   $2 = 采样间隔秒数，默认 2
# 环境变量：
#   GPU_BURN_PRECISION = fp32（默认）或 fp64；fp64 会向 gpu-burn 传入 -d
#
# 特点：
#   1. 为本机实际 GPU 架构构建并校验 /opt 缓存 fatbin，再并发运行 gpu-burn
#   2. nvidia-smi 监控所有 GPU
#   3. XLSX 按 GPU index 分别统计利用率、温度、功耗、显存
#   4. 修复原脚本只显示第一张卡、功耗混算的问题
# ============================================================

DURATION="${1:-43200}"
INTERVAL="${2:-2}"
GPU_BURN_PRECISION="${GPU_BURN_PRECISION:-fp32}"
TIME_TAG="$(date +%F_%H%M%S)"

WORKDIR="$(pwd)"
GPU_BURN_ARCHIVE_URL="http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/gpu-burn-master.zip"
GPU_BURN_DIR="/opt/software/gpu-burn"
GPU_BURN_ARCHIVE_PATH="/opt/software/gpu-burn-master.zip"

BURN_LOG="${WORKDIR}/stress_gpu_${TIME_TAG}.log"
GPU_BURN_BUILD_LOCK="/opt/software/.hpcdeploy-gpu-burn.lock"
GPU_BURN_BUILD_STATE="${GPU_BURN_DIR}/.hpcdeploy-gpu-burn-build-state"
MON_LOG="${WORKDIR}/gpu_monitor_${TIME_TAG}.csv"
GPU_META_CSV="${WORKDIR}/gpu_metadata_${TIME_TAG}.csv"
REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.txt"
XLSX_REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.xlsx"

case "$GPU_BURN_PRECISION" in
    fp32|fp64) ;;
    *)
        echo "[ERROR] GPU_BURN_PRECISION must be fp32 or fp64"
        exit 2
        ;;
esac

log() {
    echo "$(date '+%F %T') $*"
}

epel_repo_enabled() {
    dnf -q repolist --enabled 2>/dev/null |
        awk 'NR > 1 {print $1}' |
        grep -Eq '^epel(/|$)'
}

rpm_package_manager() {
    if command -v dnf >/dev/null 2>&1; then
        echo dnf
    elif command -v yum >/dev/null 2>&1; then
        echo yum
    else
        echo "[ERROR] No supported RPM package manager found" >&2
        return 1
    fi
}

dnf_install_with_retry() {
    local package_manager attempt delay
    local -a refresh_args=()

    package_manager="$(rpm_package_manager)" || return 1
    attempt=1
    while [ "$attempt" -le "$DNF_INSTALL_ATTEMPTS" ]; do
        refresh_args=()
        if [ "$attempt" -gt 1 ] && [ "$package_manager" = "dnf" ]; then
            refresh_args=(--refresh)
        fi
        echo "[INFO] Dependency install attempt ${attempt}/${DNF_INSTALL_ATTEMPTS}: $*"
        if "$package_manager" -y \
            --setopt="minrate=${DNF_MINRATE}" \
            --setopt="timeout=${DNF_TIMEOUT}" \
            --setopt="retries=${DNF_RETRIES}" \
            "${refresh_args[@]}" install "$@"; then
            return 0
        fi
        if [ "$attempt" -ge "$DNF_INSTALL_ATTEMPTS" ]; then
            break
        fi
        if [ "$attempt" -eq 1 ]; then delay=5; else delay=15; fi
        echo "[WARN] Dependency install attempt ${attempt}/${DNF_INSTALL_ATTEMPTS} failed; retrying in ${delay}s."
        sleep "$delay"
        attempt=$((attempt + 1))
    done
    return 1
}

ensure_epel_repo() {
    if epel_repo_enabled; then
        echo "[INFO] EPEL repository already enabled; skip epel-release install."
    else
        if ! dnf_install_with_retry epel-release; then
            echo "[ERROR] Dependency installation failed after ${DNF_INSTALL_ATTEMPTS} attempts: epel-release"
            return 1
        fi
    fi
}

install_deps() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "[ERROR] 请使用 root 用户运行，或使用 sudo"
        exit 1
    fi

    if ! command -v nvidia-smi >/dev/null 2>&1; then
        echo "[ERROR] nvidia-smi not found，请先安装 NVIDIA 驱动"
        exit 1
    fi

    local -a rpm_packages=()
    local openpyxl_missing=0

    command -v make >/dev/null 2>&1 || rpm_packages+=(make)
    command -v wget >/dev/null 2>&1 || rpm_packages+=(wget)
    command -v unzip >/dev/null 2>&1 || rpm_packages+=(unzip)

    if ! command -v gcc >/dev/null 2>&1 && ! command -v cc >/dev/null 2>&1; then
        rpm_packages+=(gcc)
    fi

    if ! command -v g++ >/dev/null 2>&1 && ! command -v c++ >/dev/null 2>&1; then
        rpm_packages+=(gcc-c++)
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        rpm_packages+=(python3 python3-pip)
        openpyxl_missing=1
    elif ! python3 - <<'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
    then
        openpyxl_missing=1
        if ! python3 -m pip --version >/dev/null 2>&1; then
            rpm_packages+=(python3-pip)
        fi
    fi

    if [ "${#rpm_packages[@]}" -eq 0 ] && [ "$openpyxl_missing" -eq 0 ]; then
        echo "[INFO] Dependencies already installed, skip install."
        return 0
    fi

    echo "[INFO] Missing dependencies detected, installing..."

    if [ -f /etc/redhat-release ]; then
        ensure_epel_repo || return 1
        if [ "${#rpm_packages[@]}" -gt 0 ] && ! dnf_install_with_retry "${rpm_packages[@]}"; then
            echo "[ERROR] Dependency installation failed after ${DNF_INSTALL_ATTEMPTS} attempts: ${rpm_packages[*]}"
            return 1
        fi

        if [ "$openpyxl_missing" -eq 1 ] && ! dnf_install_with_retry python3-openpyxl; then
            echo "[WARN] RPM package python3-openpyxl is unavailable; falling back to pip."
        fi

        if ! python3 - <<'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    elif [ -f /etc/debian_version ]; then
        apt update
        apt install -y build-essential wget unzip python3 python3-pip python3-openpyxl

        if ! python3 - <<'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    else
        echo "[ERROR] Unsupported OS"
        exit 1
    fi
}

find_cuda_home() {
    if command -v nvcc >/dev/null 2>&1; then
        local nvcc_path
        nvcc_path="$(command -v nvcc)"
        CUDA_HOME="$(cd "$(dirname "$nvcc_path")/.." && pwd)"
        export CUDA_HOME
        export PATH="$CUDA_HOME/bin:$PATH"
        export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
        echo "[INFO] nvcc found in PATH: $nvcc_path"
        echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
        return 0
    fi

    for dir in /usr/local/cuda /usr/local/cuda-13.2 /usr/local/cuda-13.1 /usr/local/cuda-13.0 /usr/local/cuda-12.8 /usr/local/cuda-12.6 /usr/local/cuda-12.4 /usr/local/cuda-12.2; do
        if [ -x "$dir/bin/nvcc" ]; then
            CUDA_HOME="$dir"
            export CUDA_HOME
            export PATH="$CUDA_HOME/bin:$PATH"
            export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
            echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
            echo "[INFO] nvcc path: $CUDA_HOME/bin/nvcc"
            return 0
        fi
    done

    for dir in /usr/local/cuda-*; do
        if [ -d "$dir" ] && [ -x "$dir/bin/nvcc" ]; then
            CUDA_HOME="$dir"
            export CUDA_HOME
            export PATH="$CUDA_HOME/bin:$PATH"
            export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
            echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
            echo "[INFO] nvcc path: $CUDA_HOME/bin/nvcc"
            return 0
        fi
    done

    echo "[WARN] nvcc not found. CUDA Toolkit may not be installed."
    return 1
}

detect_gpu_metadata() {
    if ! nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,power.limit,compute_cap --format=csv,noheader,nounits > "$GPU_META_CSV" 2>/dev/null; then
        nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,power.limit --format=csv,noheader,nounits > "$GPU_META_CSV"
    fi

    GPU_COUNT="$(wc -l < "$GPU_META_CSV" | awk '{print $1}')"

    if [ "${GPU_COUNT:-0}" -le 0 ]; then
        echo "[ERROR] 未检测到 NVIDIA GPU"
        exit 1
    fi

    echo "[INFO] Detected GPU count: $GPU_COUNT"
    echo "[INFO] GPU metadata:"
    cat "$GPU_META_CSV"
}

build_gpu_burn_if_needed() {
    find_cuda_home || true

    if ! command -v nvcc >/dev/null 2>&1; then
        echo "[ERROR] nvcc not found，无法编译 gpu-burn"
        echo "[INFO] nvidia-smi 存在说明驱动正常，但缺 CUDA Toolkit / nvcc"
        exit 1
    fi

    ensure_gpu_burn_source || {
        echo "[ERROR] gpu-burn source recovery failed: $GPU_BURN_DIR"
        exit 1
    }
}

ensure_gpu_burn_source() {
    if [ -f "$GPU_BURN_DIR/Makefile" ]; then
        echo "[INFO] Local gpu-burn source is available: $GPU_BURN_DIR"
        return 0
    fi

    # This is recovery only: normal tasks never download the source again.
    echo "[WARN] Local gpu-burn source is missing; restoring it from shared archive."
    restore_gpu_burn_source_from_archive || return 1
    echo "[INFO] Local gpu-burn source restored: $GPU_BURN_DIR"
}

refresh_gpu_burn_source_after_kernel_mismatch() {
    echo "[WARN] Confirmed gpu-burn kernel-image mismatch; fetching latest source."
    restore_gpu_burn_source_from_archive
}

restore_gpu_burn_source_from_archive() {
    local archive_temp staging_dir source_dir entry
    staging_dir="$(mktemp -d "${GPU_BURN_DIR}.hpcdeploy-download.XXXXXX")" || {
        return 1
    }

    if [ -f "$GPU_BURN_ARCHIVE_PATH" ]; then
        echo "[INFO] Reusing cached gpu-burn source archive: $GPU_BURN_ARCHIVE_PATH"
    else
        archive_temp="$(mktemp "${GPU_BURN_ARCHIVE_PATH}.download.XXXXXX")" || {
            rm -rf "$staging_dir"
            return 1
        }
        echo "[INFO] Downloading gpu-burn source archive to persistent cache: $GPU_BURN_ARCHIVE_PATH"
        wget -q -O "$archive_temp" "$GPU_BURN_ARCHIVE_URL" || {
            rm -f "$archive_temp"
            rm -rf "$staging_dir"
            return 1
        }
        if ! unzip -Z1 "$archive_temp" >/dev/null 2>&1; then
            echo "[ERROR] Downloaded gpu-burn source archive is not a readable ZIP."
            rm -f "$archive_temp"
            rm -rf "$staging_dir"
            return 1
        fi
        mv "$archive_temp" "$GPU_BURN_ARCHIVE_PATH"
        echo "[INFO] Cached gpu-burn source archive: $GPU_BURN_ARCHIVE_PATH"
    fi

    while IFS= read -r entry; do
        case "$entry" in
            /*|../*|*/../*|..)
                echo "[ERROR] Shared gpu-burn archive contains an unsafe path: $entry"
                rm -rf "$staging_dir"
                return 1
                ;;
        esac
    done < <(unzip -Z1 "$GPU_BURN_ARCHIVE_PATH")
    unzip -q "$GPU_BURN_ARCHIVE_PATH" -d "$staging_dir" || {
        rm -rf "$staging_dir"
        return 1
    }
    source_dir="$(find "$staging_dir" -mindepth 1 -maxdepth 1 -type d -print -quit)"
    if [ -z "$source_dir" ] || [ ! -f "$source_dir/Makefile" ]; then
        rm -rf "$staging_dir"
        return 1
    fi
    (
        flock -x 9
        rm -rf "$GPU_BURN_DIR"
        mv "$source_dir" "$GPU_BURN_DIR"
    ) 9>"$GPU_BURN_BUILD_LOCK" || return 1
    rmdir "$staging_dir" 2>/dev/null || true
}

gpu_burn_source_fingerprint() {
    (
        cd "$GPU_BURN_DIR" || exit 1
        sha256sum Makefile compare.cu gpu_burn-drv.cpp 2>/dev/null | sha256sum | awk '{print $1}'
    )
}

gpu_burn_cache_matches() {
    local source_fingerprint="$1" nvcc_fingerprint="$2" target_arches="$3" arch inspected_arches
    [ -x "$GPU_BURN_DIR/gpu_burn" ] && [ -f "$GPU_BURN_DIR/compare.fatbin" ] && [ -f "$GPU_BURN_BUILD_STATE" ] || return 1
    grep -Fqx "source=${source_fingerprint}" "$GPU_BURN_BUILD_STATE" || return 1
    grep -Fqx "nvcc=${nvcc_fingerprint}" "$GPU_BURN_BUILD_STATE" || return 1
    grep -Fqx "targets=${target_arches}" "$GPU_BURN_BUILD_STATE" || return 1
    inspected_arches="$(cuobjdump --list-elf "$GPU_BURN_DIR/compare.fatbin" 2>&1)" || return 1
    for arch in $target_arches; do
        printf '%s\n' "$inspected_arches" | grep -Eq "sm_${arch}([^0-9]|$)" || return 1
    done
}

ensure_gpu_burn_cached_binary() {
    local source_fingerprint nvcc_fingerprint target_arches arch inspected_arches
    local -a fatbin_flags=()
    target_arches="$(printf '%s\n' "$@" | sort -n | xargs)"
    for arch in $target_arches; do
        fatbin_flags+=("-gencode=arch=compute_${arch},code=sm_${arch}")
    done

    (
        flock -x 9
        source_fingerprint="$(gpu_burn_source_fingerprint)" || exit 1
        nvcc_fingerprint="$(nvcc --version | sha256sum | awk '{print $1}')"
        if gpu_burn_cache_matches "$source_fingerprint" "$nvcc_fingerprint" "$target_arches"; then
            echo "[INFO] Reuse verified GPU-matched fat binary: $(printf 'sm_%s ' $target_arches)"
            exit 0
        fi
        echo "[INFO] Rebuild GPU-matched fat binary cache: ${fatbin_flags[*]}"
        rm -f "$GPU_BURN_DIR/gpu_burn" "$GPU_BURN_DIR/compare.fatbin" "$GPU_BURN_DIR"/*.o "$GPU_BURN_BUILD_STATE"
        (
            cd "$GPU_BURN_DIR" || exit 1
            make clean || true
            make COMPUTE= NVCCFLAGS="${fatbin_flags[*]}" -j"$(nproc)"
        ) || exit 1
        inspected_arches="$(cuobjdump --list-elf "$GPU_BURN_DIR/compare.fatbin" 2>&1)" || exit 1
        for arch in $target_arches; do
            printf '%s\n' "$inspected_arches" | grep -Eq "sm_${arch}([^0-9]|$)" || {
                echo "[ERROR] compare.fatbin is missing verified sm_${arch} code."
                exit 1
            }
        done
        printf 'source=%s\nnvcc=%s\ntargets=%s\n' "$source_fingerprint" "$nvcc_fingerprint" "$target_arches" > "$GPU_BURN_BUILD_STATE"
        echo "[INFO] compare.fatbin verified for: $(printf 'sm_%s ' $target_arches)"
    ) 9>"$GPU_BURN_BUILD_LOCK"
}

prepare_gpu_burn_matched_binary() {
    local supported_arches arch capability
    local inspected_arches
    local -a target_arches=()
    declare -A target_seen=()

    supported_arches="$(nvcc --list-gpu-arch 2>/dev/null | tr '[:space:]' '\n' | sed -n 's/^compute_//p')"
    if [ -z "$supported_arches" ]; then
        echo "[ERROR] nvcc cannot list supported GPU architectures; refuse to build an unverified fat binary."
        return 1
    fi

    # A task-local fatbin must match only the physical GPUs on this server.
    # Do not reuse source-tree artifacts or compile unrelated architectures.
    while IFS=, read -r _ capability; do
        capability="$(echo "$capability" | xargs)"
        arch="${capability//./}"
        [ -n "$arch" ] || continue
        if ! printf '%s\n' "$supported_arches" | grep -Fxq "$arch"; then
            echo "[ERROR] CUDA Toolkit cannot build sm_${arch} required by a detected GPU."
            return 1
        fi
        if [ -z "${target_seen[$arch]:-}" ]; then
            target_arches+=("$arch")
            target_seen[$arch]=1
        fi
    done < <(nvidia-smi --query-gpu=index,compute_cap --format=csv,noheader,nounits)

    if [ "${#target_arches[@]}" -eq 0 ]; then
        echo "[ERROR] No compatible architecture was detected for the GPU fat binary cache."
        return 1
    fi

    if ! command -v cuobjdump >/dev/null 2>&1; then
        echo "[ERROR] cuobjdump is required to verify compare.fatbin target architectures."
        return 1
    fi
    ensure_gpu_burn_cached_binary "${target_arches[@]}"
}

stream_gpu_burn_output() {
    local arch="$1" gpu_ids="$2" group_log="$3" build_dir="$GPU_BURN_DIR"
    (
        cd "$build_dir" || exit 1
        CUDA_VISIBLE_DEVICES="$gpu_ids" ./gpu_burn "${BURN_ARGS[@]}" 2>&1 | tr '\r' '\n' | awk '
            /^[[:space:]]*[0-9]+(\.[0-9]+)?%/ { pct=$1; sub(/%$/, "", pct); bucket=int(pct/10); if (!(bucket in seen)) { print "[PROGRESS SAMPLE] " $0; seen[bucket]=1 }; next }
            tolower($0) ~ /cuda error|failed|xid|fallen off|couldn.t init|named symbol not found|read.*error|died|no clients are alive|aborting|error in|segmentation fault|illegal memory/ { print "[ERROR] " $0 }
        '
        exit "${PIPESTATUS[0]}"
    ) > "$group_log" 2>&1 &
    LAST_GPU_BURN_PID=$!
}

stop_gpu_burn_process_tree() {
    local pid="$1" child
    # The background wrapper owns gpu_burn and its output pipeline.  Terminate
    # descendants first so a failed attempt cannot leave a GPU load behind.
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        stop_gpu_burn_process_tree "$child"
    done
    kill "$pid" >/dev/null 2>&1 || true
}

run_gpu_burn_per_gpu() {
    local index capability arch gpu_log i
    local -a gpu_pids=() gpu_indexes=() gpu_arches=() gpu_logs=()
    declare -A gpu_arch_by_index=()

    while IFS=, read -r index capability; do
        index="$(echo "$index" | xargs)"
        capability="$(echo "$capability" | xargs)"
        arch="${capability//./}"
        if [ -z "$index" ] || [ -z "$arch" ]; then
            continue
        fi
        if [ -n "${gpu_arch_by_index[$index]:-}" ]; then
            continue
        fi
        gpu_arch_by_index[$index]="$arch"
    done < <(nvidia-smi --query-gpu=index,compute_cap --format=csv,noheader,nounits)

    if [ "${#gpu_arch_by_index[@]}" -eq 0 ]; then
        echo "[ERROR] No GPU compute capability metadata available."
        return 1
    fi

    : > "$BURN_LOG"
    BURN_EXIT=0
    prepare_gpu_burn_matched_binary || return 1

    while IFS= read -r index; do
        arch="${gpu_arch_by_index[$index]}"
        gpu_log="${WORKDIR}/stress_gpu_${TIME_TAG}_gpu${index}_sm${arch}.log"
        echo "[INFO] Start gpu-burn for GPU ${index}: SM ${arch}"
        stream_gpu_burn_output "$arch" "$index" "$gpu_log"
        gpu_pids+=("$LAST_GPU_BURN_PID")
        gpu_indexes+=("$index")
        gpu_arches+=("$arch")
        gpu_logs+=("$gpu_log")
    done < <(printf '%s\n' "${!gpu_arch_by_index[@]}" | sort -n)

    # fail fast: do not spend the remaining test duration after a confirmed
    # gpu-burn kernel-image mismatch has already made this attempt invalid.
    while :; do
        if grep -qi "no kernel image is available for execution on the device" "${WORKDIR}"/stress_gpu_"${TIME_TAG}"_gpu*.log 2>/dev/null; then
            for i in "${!gpu_pids[@]}"; do
                stop_gpu_burn_process_tree "${gpu_pids[$i]}"
            done
            for i in "${!gpu_pids[@]}"; do
                wait "${gpu_pids[$i]}" >/dev/null 2>&1 || true
            done
            if [ "${GPU_BURN_REFRESHED:-0}" != "1" ]; then
                GPU_BURN_REFRESHED=1
                refresh_gpu_burn_source_after_kernel_mismatch || return 1
                echo "[INFO] Retrying GPU stress with the refreshed gpu-burn source."
                run_gpu_burn_per_gpu
                return
            fi
            BURN_EXIT=1
            return
        fi
        local active=0
        for i in "${!gpu_pids[@]}"; do kill -0 "${gpu_pids[$i]}" >/dev/null 2>&1 && active=1; done
        [ "$active" -eq 0 ] && break
        sleep 1
    done

    for i in "${!gpu_pids[@]}"; do
        local gpu_exit=0
        if ! wait "${gpu_pids[$i]}"; then
            gpu_exit=1
            BURN_EXIT=1
        fi
        printf '[GPU %s SM %s]\n' "${gpu_indexes[$i]}" "${gpu_arches[$i]}" >> "$BURN_LOG"
        cat "${gpu_logs[$i]}" >> "$BURN_LOG"
        printf '[SUMMARY] GPU %s SM %s exit=%s\n' \
            "${gpu_indexes[$i]}" "${gpu_arches[$i]}" "$gpu_exit" >> "$BURN_LOG"
    done

}

main() {
    echo "[STAGE] dependency_check_start"
    install_deps || exit 1
    echo "[STAGE] dependency_check_done"

    echo "======================================"
    echo "GPU Stress Test Start"
    echo "Duration : ${DURATION}s"
    echo "Interval : ${INTERVAL}s"
    echo "Precision: ${GPU_BURN_PRECISION^^}"
    echo "Workdir  : ${WORKDIR}"
    echo "Burn Dir : ${GPU_BURN_DIR}"
    echo "======================================"

    detect_gpu_metadata
    build_gpu_burn_if_needed

    if command -v nvcc >/dev/null 2>&1; then
        CUDA_TOOLKIT="$(nvcc --version | grep release | sed -E 's/.*V([0-9.]+).*/\1/' || true)"
    else
        CUDA_TOOLKIT="Not Found"
    fi

    NVIDIA_DRIVER_VERSION="$(
        nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null \
            | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
            | sort -u \
            | paste -sd ',' -
    )"
    NVIDIA_SMI_PATH="$(command -v nvidia-smi || true)"

    echo "[INFO] nvidia-smi path: ${NVIDIA_SMI_PATH}"
    echo "[INFO] NVIDIA Driver Version: ${NVIDIA_DRIVER_VERSION:-Unknown}"
    echo "[INFO] CUDA Toolkit Version: ${CUDA_TOOLKIT:-Unknown}"

    echo "[INFO] Start monitoring all GPUs..."
    nvidia-smi \
        --query-gpu=timestamp,index,name,utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total \
        --format=csv \
        -l "$INTERVAL" > "$MON_LOG" &

    MON_PID=$!
    sleep 2

    BURN_ARGS=("$DURATION")
    if [ "$GPU_BURN_PRECISION" = "fp64" ]; then
        BURN_ARGS=(-d "$DURATION")
    fi
    echo "[STAGE] stress_start"
    echo "[INFO] Start gpu-burn (${GPU_BURN_PRECISION^^}) with one process per GPU."
    run_gpu_burn_per_gpu || BURN_EXIT=1

    kill "$MON_PID" >/dev/null 2>&1 || true
    wait "$MON_PID" >/dev/null 2>&1 || true
    sleep 1

    echo
    echo "======================================"
    echo "压测完成，开始生成 TXT/XLSX 报告"
    echo "请勿按 Ctrl+C"
    echo "======================================"
    echo

    ERROR_COUNT="$(grep -E "errors:" "$BURN_LOG" | awk '{for(i=1;i<=NF;i++){if($i=="errors:"){print $(i+1)}}}' | sort -nr | head -1 || true)"
    ERROR_COUNT="${ERROR_COUNT:-0}"

    GPU_ERROR="$(grep -Ei "cuda error|failed|xid|fallen off|couldn't init|named symbol not found|read.*error|died|no clients are alive|aborting|error in|segmentation fault|illegal memory" "$BURN_LOG" || true)"
    printf '[SUMMARY] gpu-burn exit=%s, max_errors=%s\n' "$BURN_EXIT" "$ERROR_COUNT" >> "$BURN_LOG"

    RESULT="PASS"
    REASON="No error detected."

    if [ "$BURN_EXIT" != "0" ]; then
        RESULT="FAIL"
        REASON="gpu-burn exited abnormally. Exit code: ${BURN_EXIT}"
    fi

    if [ "$ERROR_COUNT" != "0" ]; then
        RESULT="FAIL"
        REASON="gpu-burn reported calculation errors."
    fi

    if [ -n "$GPU_ERROR" ]; then
        RESULT="FAIL"
        REASON="GPU/CUDA/gpu-burn runtime error detected."
    fi

    export DURATION INTERVAL GPU_BURN_PRECISION TIME_TAG WORKDIR GPU_BURN_DIR BURN_LOG MON_LOG GPU_META_CSV REPORT XLSX_REPORT
    export BURN_EXIT ERROR_COUNT RESULT REASON CUDA_TOOLKIT NVIDIA_DRIVER_VERSION NVIDIA_SMI_PATH GPU_COUNT

    python3 - <<'PYEOF'
import csv
import os
import re
from pathlib import Path
from statistics import mean

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter


duration = os.environ.get("DURATION", "")
interval = os.environ.get("INTERVAL", "")
gpu_burn_precision = os.environ.get("GPU_BURN_PRECISION", "fp32").upper()
workdir = os.environ.get("WORKDIR", "")
gpu_burn_dir = os.environ.get("GPU_BURN_DIR", "")
burn_log = Path(os.environ["BURN_LOG"])
mon_log = Path(os.environ["MON_LOG"])
gpu_meta_csv = Path(os.environ["GPU_META_CSV"])
report = Path(os.environ["REPORT"])
xlsx = Path(os.environ["XLSX_REPORT"])

burn_exit = os.environ.get("BURN_EXIT", "")
error_count = os.environ.get("ERROR_COUNT", "0")
result = os.environ.get("RESULT", "UNKNOWN")
reason = os.environ.get("REASON", "")
cuda_toolkit = os.environ.get("CUDA_TOOLKIT", "")
nvidia_driver_version = os.environ.get("NVIDIA_DRIVER_VERSION", "")
nvidia_smi_path = os.environ.get("NVIDIA_SMI_PATH", "")


def clean_text(v):
    if v is None:
        return ""
    return str(v).strip()


def to_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if "N/A" in s.upper() or "NOT SUPPORTED" in s.upper() or "UNKNOWN" in s.upper():
        return None
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return None
    try:
        return float(s)
    except Exception:
        return None


def stat(values):
    nums = [v for v in values if v is not None]
    if not nums:
        return {
            "avg": "N/A",
            "min": "N/A",
            "max": "N/A",
        }
    return {
        "avg": round(mean(nums), 2),
        "min": round(min(nums), 2),
        "max": round(max(nums), 2),
    }


def parse_gpu_meta(path):
    rows = []
    if not path.exists():
        return rows

    with path.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            row = [clean_text(x) for x in row]
            if not row:
                continue

            # index,name,uuid,driver_version,memory.total,power.limit,compute_cap
            rows.append({
                "index": row[0] if len(row) > 0 else "",
                "name": row[1] if len(row) > 1 else "",
                "uuid": row[2] if len(row) > 2 else "",
                "driver": row[3] if len(row) > 3 else "",
                "mem_total": row[4] if len(row) > 4 else "",
                "power_limit": row[5] if len(row) > 5 else "",
                "compute_cap": row[6] if len(row) > 6 else "",
            })
    return rows


def parse_monitor(path):
    rows = []
    if not path.exists():
        return rows

    with path.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for raw in reader:
            if len(raw) < 8:
                continue

            timestamp = clean_text(raw[0])
            index = clean_text(raw[1])
            name = clean_text(raw[2])

            util = to_float(raw[3])
            temp = to_float(raw[4])
            power = to_float(raw[5])
            mem_used = to_float(raw[6])
            mem_total = to_float(raw[7])

            rows.append({
                "timestamp": timestamp,
                "index": index,
                "name": name,
                "util": util,
                "temp": temp,
                "power": power,
                "mem_used": mem_used,
                "mem_total": mem_total,
                "raw": raw,
            })

    return rows


def parse_gflops(path):
    vals = []
    if not path.exists():
        return stat(vals)

    text = path.read_text(errors="ignore")
    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s+Gflop/s", text):
        vals.append(float(m.group(1)))
    return stat(vals)


gpu_meta = parse_gpu_meta(gpu_meta_csv)
mon_rows = parse_monitor(mon_log)
gflops_stat = parse_gflops(burn_log)

by_gpu = {}
for meta in gpu_meta:
    idx = meta["index"]
    by_gpu[idx] = {
        "meta": meta,
        "rows": [],
    }

for row in mon_rows:
    idx = row["index"]
    if idx not in by_gpu:
        by_gpu[idx] = {
            "meta": {
                "index": idx,
                "name": row["name"],
                "uuid": "",
                "driver": "",
                "mem_total": "",
                "power_limit": "",
                "compute_cap": "",
            },
            "rows": [],
        }
    by_gpu[idx]["rows"].append(row)

gpu_summary = []
per_gpu_fail_reasons = []

for idx in sorted(by_gpu.keys(), key=lambda x: int(x) if str(x).isdigit() else 9999):
    item = by_gpu[idx]
    rows = item["rows"]
    meta = item["meta"]

    util_s = stat([r["util"] for r in rows])
    temp_s = stat([r["temp"] for r in rows])
    power_s = stat([r["power"] for r in rows])
    mem_s = stat([r["mem_used"] for r in rows])

    samples = len(rows)
    max_util = util_s["max"]

    gpu_result = "PASS"
    gpu_reason = "Observed normal monitor data."

    if samples <= 0:
        gpu_result = "FAIL"
        gpu_reason = "No monitor data for this GPU."
    elif isinstance(max_util, (int, float)) and max_util < 90:
        gpu_result = "FAIL"
        gpu_reason = "GPU utilization did not reach 90%."
    elif max_util == "N/A":
        gpu_result = "WARN"
        gpu_reason = "GPU utilization is N/A."

    if gpu_result == "FAIL":
        per_gpu_fail_reasons.append(f"GPU {idx}: {gpu_reason}")

    gpu_summary.append({
        "index": idx,
        "name": meta.get("name", ""),
        "uuid": meta.get("uuid", ""),
        "driver": meta.get("driver", ""),
        "compute_cap": meta.get("compute_cap", ""),
        "mem_total": meta.get("mem_total", ""),
        "power_limit": meta.get("power_limit", ""),
        "samples": samples,
        "util_avg": util_s["avg"],
        "util_min": util_s["min"],
        "util_max": util_s["max"],
        "temp_avg": temp_s["avg"],
        "temp_min": temp_s["min"],
        "temp_max": temp_s["max"],
        "power_avg": power_s["avg"],
        "power_min": power_s["min"],
        "power_max": power_s["max"],
        "mem_avg": mem_s["avg"],
        "mem_min": mem_s["min"],
        "mem_max": mem_s["max"],
        "result": gpu_result,
        "reason": gpu_reason,
    })

final_result = result
final_reason = reason

if result == "PASS" and per_gpu_fail_reasons:
    final_result = "FAIL"
    final_reason = "; ".join(per_gpu_fail_reasons)


lines = []
lines.append("GPU 多卡稳定性压力测试报告")
lines.append("")
lines.append("一、测试概述")
lines.append("本次测试使用 gpu-burn 对系统中所有可见 NVIDIA GPU 进行压力测试，并使用 nvidia-smi 采集所有 GPU 的利用率、温度、功耗和显存占用。")
lines.append("")
lines.append("二、测试环境")
lines.append(f"GPU 数量              : {len(gpu_summary)}")
lines.append(f"NVIDIA 驱动版本       : {nvidia_driver_version}")
lines.append(f"CUDA Toolkit 版本     : {cuda_toolkit}")
lines.append(f"nvidia-smi            : {nvidia_smi_path}")
lines.append(f"测试时长              : {duration} 秒")
lines.append(f"采样间隔              : {interval} 秒")
lines.append(f"计算精度              : {gpu_burn_precision}")
lines.append(f"工作目录              : {workdir}")
lines.append(f"gpu-burn目录          : {gpu_burn_dir}")
lines.append("")
lines.append("三、GPU 设备清单")
for g in gpu_summary:
    lines.append(f"GPU {g['index']} | {g['name']} | Memory={g['mem_total']} MiB | PowerLimit={g['power_limit']} W | ComputeCap={g['compute_cap']} | UUID={g['uuid']}")
lines.append("")
lines.append("四、每卡测试结果汇总")
for g in gpu_summary:
    lines.append(f"GPU {g['index']} - {g['name']}")
    lines.append(f"  Samples              : {g['samples']}")
    lines.append(f"  Util Avg/Min/Max     : {g['util_avg']} / {g['util_min']} / {g['util_max']} %")
    lines.append(f"  Temp Avg/Min/Max     : {g['temp_avg']} / {g['temp_min']} / {g['temp_max']} °C")
    lines.append(f"  Power Avg/Min/Max    : {g['power_avg']} / {g['power_min']} / {g['power_max']} W")
    lines.append(f"  Mem Avg/Min/Max      : {g['mem_avg']} / {g['mem_min']} / {g['mem_max']} MiB")
    lines.append(f"  Result               : {g['result']}")
    lines.append(f"  Reason               : {g['reason']}")
    lines.append("")
lines.append("五、gpu-burn 结果")
lines.append(f"平均算力              : {gflops_stat['avg']} Gflop/s")
lines.append(f"最低算力              : {gflops_stat['min']} Gflop/s")
lines.append(f"最高算力              : {gflops_stat['max']} Gflop/s")
lines.append(f"计算错误              : {error_count}")
lines.append(f"gpu-burn退出码        : {burn_exit}")
lines.append("")
lines.append("六、综合判定")
lines.append(f"测试结果              : {final_result}")
lines.append(f"判定原因              : {final_reason}")
lines.append("")
lines.append("七、报告文件")
lines.append(f"压测日志              : {burn_log}")
lines.append(f"监控日志              : {mon_log}")
lines.append(f"GPU元数据             : {gpu_meta_csv}")
lines.append(f"Excel报告             : {xlsx}")

report.write_text("\n".join(lines), encoding="utf-8")


wb = Workbook()
ws = wb.active
ws.title = "Summary"
meta_ws = wb.create_sheet("GPU_Metadata")
mon_ws = wb.create_sheet("MonitorCSV")
burn_ws = wb.create_sheet("BurnLog")
raw_ws = wb.create_sheet("RawReport")

dark = "1F4E78"
gray = "F2F2F2"
green = "C6EFCE"
red = "FFC7CE"
yellow = "FFEB9C"
white = "FFFFFF"

border = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

def style_cell(cell, bold=False, fill=None, color=None):
    cell.border = border
    cell.alignment = Alignment(wrap_text=True, vertical="center")
    if bold:
        cell.font = Font(bold=True, color=color or "000000")
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)

def title(ws, row, text, end_col=18):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(size=16, bold=True, color=white)
    c.fill = PatternFill("solid", fgColor=dark)
    c.alignment = Alignment(horizontal="center", vertical="center")
    return row + 1

def section(ws, row, text, end_col=18):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, color=white)
    c.fill = PatternFill("solid", fgColor=dark)
    return row + 1

def kv(ws, row, k, v):
    ws.cell(row=row, column=1, value=k)
    ws.cell(row=row, column=2, value=v)
    style_cell(ws.cell(row=row, column=1), bold=True, fill=gray)
    style_cell(ws.cell(row=row, column=2))
    return row + 1

r = 1
r = title(ws, r, "GPU 多卡稳定性压力测试报告")
r += 1

r = section(ws, r, "一、测试环境")
for k, v in [
    ("GPU 数量", len(gpu_summary)),
    ("测试时长", f"{duration} 秒"),
    ("采样间隔", f"{interval} 秒"),
    ("计算精度", gpu_burn_precision),
    ("NVIDIA 驱动版本", nvidia_driver_version),
    ("CUDA Toolkit 版本", cuda_toolkit),
    ("nvidia-smi", nvidia_smi_path),
    ("工作目录", workdir),
    ("gpu-burn目录", gpu_burn_dir),
]:
    r = kv(ws, r, k, v)

r += 1
r = section(ws, r, "二、综合判定")
r = kv(ws, r, "测试结果", final_result)
ws.cell(row=r-1, column=2).fill = PatternFill("solid", fgColor=green if final_result == "PASS" else red)
ws.cell(row=r-1, column=2).font = Font(bold=True)
r = kv(ws, r, "判定原因", final_reason)
r = kv(ws, r, "gpu-burn退出码", burn_exit)
r = kv(ws, r, "计算错误", error_count)
r = kv(ws, r, "平均算力", f"{gflops_stat['avg']} Gflop/s")
r = kv(ws, r, "最低算力", f"{gflops_stat['min']} Gflop/s")
r = kv(ws, r, "最高算力", f"{gflops_stat['max']} Gflop/s")

r += 1
r = section(ws, r, "三、每张 GPU 汇总")

headers = [
    "GPU", "型号", "UUID", "驱动", "ComputeCap", "显存总量(MiB)", "功耗上限(W)", "采样数",
    "利用率平均(%)", "利用率最低(%)", "利用率最高(%)",
    "温度平均(°C)", "温度最低(°C)", "温度最高(°C)",
    "功耗平均(W)", "功耗最低(W)", "功耗最高(W)",
    "显存平均(MiB)", "显存最低(MiB)", "显存最高(MiB)",
    "结果", "原因",
]

for c, h in enumerate(headers, 1):
    cell = ws.cell(row=r, column=c, value=h)
    style_cell(cell, bold=True, fill=dark, color=white)
r += 1

for g in gpu_summary:
    values = [
        g["index"], g["name"], g["uuid"], g["driver"], g["compute_cap"], g["mem_total"], g["power_limit"], g["samples"],
        g["util_avg"], g["util_min"], g["util_max"],
        g["temp_avg"], g["temp_min"], g["temp_max"],
        g["power_avg"], g["power_min"], g["power_max"],
        g["mem_avg"], g["mem_min"], g["mem_max"],
        g["result"], g["reason"],
    ]
    for c, v in enumerate(values, 1):
        cell = ws.cell(row=r, column=c, value=v)
        style_cell(cell)
        if c == 21:
            if v == "PASS":
                cell.fill = PatternFill("solid", fgColor=green)
            elif v == "WARN":
                cell.fill = PatternFill("solid", fgColor=yellow)
            else:
                cell.fill = PatternFill("solid", fgColor=red)
            cell.font = Font(bold=True)
    r += 1

for col in range(1, len(headers) + 1):
    ws.column_dimensions[get_column_letter(col)].width = 18
ws.column_dimensions["B"].width = 32
ws.column_dimensions["C"].width = 42
ws.column_dimensions["V"].width = 42

# GPU_Metadata sheet
meta_headers = ["index", "name", "uuid", "driver_version", "memory.total MiB", "power.limit W", "compute_cap"]
meta_ws.append(meta_headers)
for cell in meta_ws[1]:
    style_cell(cell, bold=True, fill=dark, color=white)

for g in gpu_summary:
    meta_ws.append([
        g["index"], g["name"], g["uuid"], g["driver"], g["mem_total"], g["power_limit"], g["compute_cap"]
    ])

for row in meta_ws.iter_rows():
    for cell in row:
        style_cell(cell)
for col in range(1, 8):
    meta_ws.column_dimensions[get_column_letter(col)].width = 24
meta_ws.column_dimensions["B"].width = 32
meta_ws.column_dimensions["C"].width = 42

# MonitorCSV sheet: normalized numeric table
mon_headers = ["timestamp", "index", "name", "utilization.gpu %", "temperature.gpu C", "power.draw W", "memory.used MiB", "memory.total MiB"]
mon_ws.append(mon_headers)
for cell in mon_ws[1]:
    style_cell(cell, bold=True, fill=dark, color=white)

for row in mon_rows:
    mon_ws.append([
        row["timestamp"], row["index"], row["name"],
        row["util"], row["temp"], row["power"], row["mem_used"], row["mem_total"]
    ])

for row in mon_ws.iter_rows():
    for cell in row:
        style_cell(cell)

for col in range(1, len(mon_headers) + 1):
    mon_ws.column_dimensions[get_column_letter(col)].width = 22
mon_ws.column_dimensions["A"].width = 28
mon_ws.column_dimensions["C"].width = 32

# BurnLog sheet
if burn_log.exists():
    for line in burn_log.read_text(errors="ignore").splitlines():
        burn_ws.append([line])
else:
    burn_ws.append(["Burn log not found"])
burn_ws.column_dimensions["A"].width = 140
for row in burn_ws.iter_rows():
    for cell in row:
        style_cell(cell)

# RawReport sheet
for line in report.read_text(errors="ignore").splitlines():
    raw_ws.append([line])
raw_ws.column_dimensions["A"].width = 140
for row in raw_ws.iter_rows():
    for cell in row:
        style_cell(cell)

# Charts: one chart per key metric from normalized MonitorCSV
if mon_ws.max_row > 2:
    chart_positions = [
        ("GPU 利用率(%)", 4, "X3"),
        ("GPU 温度(°C)", 5, "X20"),
        ("GPU 功耗(W)", 6, "X37"),
        ("显存占用(MiB)", 7, "X54"),
    ]

    for chart_title, col, pos in chart_positions:
        chart = LineChart()
        chart.title = chart_title
        chart.y_axis.title = chart_title
        chart.x_axis.title = "Sample"
        data = Reference(mon_ws, min_col=col, min_row=1, max_row=mon_ws.max_row)
        chart.add_data(data, titles_from_data=True)
        chart.height = 8
        chart.width = 18
        ws.add_chart(chart, pos)

for sheet in wb.worksheets:
    sheet.freeze_panes = "A2"

# Do not expose the final filename until openpyxl has finished writing the ZIP
# container.  The platform polls for *.xlsx and would otherwise be able to
# collect a partially-written workbook.
tmp_xlsx = xlsx.with_suffix(xlsx.suffix + ".tmp")
wb.save(tmp_xlsx)
os.replace(tmp_xlsx, xlsx)

print(f"Text Report : {report}")
print(f"XLSX Report : {xlsx}")
print(f"Final Result: {final_result}")
print(f"Reason      : {final_reason}")
PYEOF

    echo
    echo "======================================"
    echo "GPU Stress Test Finished"
    echo "Result      : $(grep -E '^测试结果' "$REPORT" | tail -1 | awk -F':' '{print $2}' | xargs || echo "$RESULT")"
    echo "Reason      : $(grep -E '^判定原因' "$REPORT" | tail -1 | awk -F':' '{print $2}' | xargs || echo "$REASON")"
    echo "GPU Count   : ${GPU_COUNT}"
    echo "Burn Log    : ${BURN_LOG}"
    echo "Monitor Log : ${MON_LOG}"
    echo "GPU Meta    : ${GPU_META_CSV}"
    echo "Text Report : ${REPORT}"
    echo "XLSX Report : ${XLSX_REPORT}"
    echo "======================================"
}

main "$@"
