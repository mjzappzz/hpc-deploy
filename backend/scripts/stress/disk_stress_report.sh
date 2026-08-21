#!/bin/bash

set -e

SCRIPT_VERSION="2026.08.21.5"

DNF_MINRATE="${HPCDEPLOY_DNF_MINRATE:-51200}"
DNF_TIMEOUT="${HPCDEPLOY_DNF_TIMEOUT:-30}"
DNF_RETRIES="${HPCDEPLOY_DNF_RETRIES:-2}"
DNF_INSTALL_ATTEMPTS="${HPCDEPLOY_DNF_INSTALL_ATTEMPTS:-3}"

echo "[STAGE] dependency_check_start"
echo "[INFO] Checking and installing dependencies..."

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

    local -a rpm_packages=()
    local openpyxl_missing=0

    if ! command -v fio >/dev/null 2>&1; then
        rpm_packages+=(fio)
    fi
    if ! command -v iostat >/dev/null 2>&1; then
        rpm_packages+=(sysstat)
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        rpm_packages+=(python3 python3-pip)
        openpyxl_missing=1
    else
        if ! python3 - << 'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            openpyxl_missing=1
            if ! python3 -m pip --version >/dev/null 2>&1; then
                rpm_packages+=(python3-pip)
            fi
        fi
    fi

    if [ "${#rpm_packages[@]}" -eq 0 ] && [ "$openpyxl_missing" -eq 0 ]; then
        echo "[INFO] Dependencies already installed, skip install."
        return 0
    fi

    echo "[INFO] Missing dependencies detected, installing..."

    if [ -f /etc/redhat-release ]; then
        echo "[INFO] Detected RHEL/CentOS/Rocky/Alma"
        ensure_epel_repo || return 1
        if [ "${#rpm_packages[@]}" -gt 0 ] && ! dnf_install_with_retry "${rpm_packages[@]}"; then
            echo "[ERROR] Dependency installation failed after ${DNF_INSTALL_ATTEMPTS} attempts: ${rpm_packages[*]}"
            return 1
        fi

        if [ "$openpyxl_missing" -eq 1 ] && ! dnf_install_with_retry python3-openpyxl; then
            echo "[WARN] RPM package python3-openpyxl is unavailable; falling back to pip."
        fi

        if ! python3 - << 'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    elif [ -f /etc/debian_version ]; then
        echo "[INFO] Detected Debian/Ubuntu"
        apt update
        apt install -y fio sysstat python3 python3-pip python3-openpyxl

        if ! python3 - << 'PYCHK' >/dev/null 2>&1
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

install_deps || exit 1

echo "[STAGE] dependency_check_done"
echo "[INFO] Dependency check done."

DURATION=${1:-43200}
INTERVAL=${2:-2}
TEST_DIR=${3:-$(pwd)}

TIME_TAG=$(date +%F_%H%M%S)
WORKDIR=$(pwd)

STRESS_LOG="${WORKDIR}/fio_disk_${TIME_TAG}.log"
FIO_JSON="${WORKDIR}/fio_performance_${TIME_TAG}.json"
FIO_DURABILITY_JSON="${WORKDIR}/fio_durability_${TIME_TAG}.json"
MON_LOG="${WORKDIR}/disk_monitor_${TIME_TAG}.csv"
ERR_LOG="${WORKDIR}/disk_error_${TIME_TAG}.log"
REPORT="${WORKDIR}/disk_stress_report_${TIME_TAG}.txt"
REPORT_TARGET_SUFFIX="$(printf '%s' "${TEST_DIR#/}" | tr '/' '_')"
if [ "$TEST_DIR" = "/" ]; then
    REPORT_TARGET_SUFFIX="root"
fi
XLSX_REPORT="${WORKDIR}/disk_stress_report_${TIME_TAG}_${REPORT_TARGET_SUFFIX}.xlsx"

CRITICAL_ERR_PATTERN="i/o error|blk_update_request|buffer i/o error|nvme.*error|reset controller|aborting command|medium error|read error|write error|filesystem error|xfs.*error|ext4.*error|bad sector|uncorrected error"

GIB=$((1024 * 1024 * 1024))
MIN_SAFETY_RESERVE_BYTES=$((20 * GIB))
HDD_PROFILE_WORKERS=2
HDD_PROFILE_BYTES=1G
SSD_WORKERS=4
SSD_BYTES=2G
NVME_WORKERS=8
NVME_BYTES=2G
# Explicit fio workload: 4 KiB random mixed I/O, 70% writes, direct I/O and a
# durable flush after each write. This avoids stress-ng's implicit read defaults.
FIO_RW="randrw"
FIO_RWMIXWRITE=70
FIO_BS="4k"
FIO_PERFORMANCE_IOENGINE="libaio"
FIO_VERIFY="crc32c"
FIO_PATH="performance: rw=${FIO_RW},rwmixwrite=${FIO_RWMIXWRITE},bs=${FIO_BS},direct=1,ioengine=${FIO_PERFORMANCE_IOENGINE}; durability: randwrite,fdatasync=1,verify=${FIO_VERIFY}"

bytes_for_gib() {
    printf '%s' "$(( $1 * GIB ))"
}

resolve_backing_device() {
    local source="$1"
    local resolved

    resolved=$(lsblk -s -n -r -o NAME,TYPE "$source" 2>/dev/null | awk '$2 == "disk" {print $1; exit}')
    if [ -z "$resolved" ]; then
        resolved=$(lsblk -no PKNAME "$source" 2>/dev/null | head -1)
    fi
    if [ -z "$resolved" ]; then
        resolved=$(basename "$source")
    fi
    printf '%s' "$resolved"
}

select_disk_profile() {
    local rota="$1"
    local tran="$2"
    local device="$3"

    HDD_WORKERS=$HDD_PROFILE_WORKERS
    HDD_BYTES=$HDD_PROFILE_BYTES
    DISK_PROFILE="unknown-conservative"

    if [ "$tran" = "nvme" ] || [[ "$device" == nvme* ]]; then
        HDD_WORKERS=$NVME_WORKERS
        HDD_BYTES=$NVME_BYTES
        DISK_PROFILE="nvme"
    elif [ "$rota" = "0" ]; then
        HDD_WORKERS=$SSD_WORKERS
        HDD_BYTES=$SSD_BYTES
        DISK_PROFILE="ssd"
    elif [ "$rota" = "1" ]; then
        DISK_PROFILE="hdd"
    fi
}

calculate_safety_reserve() {
    local total_bytes="$1"
    local percentage_reserve=$((total_bytes / 10))

    SAFETY_RESERVE_BYTES=$percentage_reserve
    if [ "$SAFETY_RESERVE_BYTES" -lt "$MIN_SAFETY_RESERVE_BYTES" ]; then
        SAFETY_RESERVE_BYTES=$MIN_SAFETY_RESERVE_BYTES
    fi
}

fit_auto_profile_to_capacity() {
    local available_bytes="$1"
    local capacity_budget=$((available_bytes - SAFETY_RESERVE_BYTES))
    local workset_bytes

    while [ "$HDD_WORKERS" -gt 1 ]; do
        workset_bytes=$((HDD_WORKERS * $(bytes_for_gib "${HDD_BYTES%G}")))
        [ "$workset_bytes" -le "$capacity_budget" ] && return
        HDD_WORKERS=$((HDD_WORKERS - 1))
        DISK_PROFILE="${DISK_PROFILE}-capacity-limited"
    done

    if [ "$HDD_BYTES" != "1G" ]; then
        HDD_BYTES=1G
        DISK_PROFILE="${DISK_PROFILE}-capacity-limited"
    fi
}

ensure_capacity_budget() {
    local total_bytes="$1"
    local available_bytes="$2"
    local workset_bytes="$3"

    calculate_safety_reserve "$total_bytes"

    if [ "$available_bytes" -le "$SAFETY_RESERVE_BYTES" ] || \
       [ "$workset_bytes" -gt $((available_bytes - SAFETY_RESERVE_BYTES)) ]; then
        echo "[ERROR] Available capacity is below the automatic disk stress safety budget."
        echo "[ERROR] Available bytes: ${available_bytes}; safety reserve bytes: ${SAFETY_RESERVE_BYTES}; requested workset bytes: ${workset_bytes}."
        exit 2
    fi
}

mkdir -p "$TEST_DIR"

MOUNT_SRC=$(df -P "$TEST_DIR" | awk 'NR==2 {print $1}')
MOUNT_POINT=$(df -P "$TEST_DIR" | awk 'NR==2 {print $6}')
FS_TYPE=$(df -T "$TEST_DIR" | awk 'NR==2 {print $2}')
DISK_DEV=$(resolve_backing_device "$MOUNT_SRC")
DISK_ROTA=$(lsblk -dn -o ROTA "/dev/${DISK_DEV}" 2>/dev/null | xargs || true)
DISK_TRAN=$(lsblk -dn -o TRAN "/dev/${DISK_DEV}" 2>/dev/null | xargs || true)
TOTAL_BYTES=$(df -B1 --output=size "$TEST_DIR" | awk 'NR==2 {print $1}')
AVAILABLE_BYTES=$(df -B1 --output=avail "$TEST_DIR" | awk 'NR==2 {print $1}')

AUTO_PROFILE=1
if [ -n "${WORKERS+x}" ]; then
    AUTO_PROFILE=0
    HDD_WORKERS=$WORKERS
    HDD_BYTES=20G
    DISK_PROFILE="manual-workers"
else
    select_disk_profile "$DISK_ROTA" "$DISK_TRAN" "$DISK_DEV"
    calculate_safety_reserve "$TOTAL_BYTES"
    fit_auto_profile_to_capacity "$AVAILABLE_BYTES"
fi

case "$HDD_WORKERS" in
    ''|*[!0-9]*) echo "[ERROR] WORKERS must be a positive integer"; exit 2 ;;
esac
[ "$HDD_WORKERS" -lt 1 ] && { echo "[ERROR] WORKERS must be greater than zero"; exit 2; }

WORKSET_BYTES=$((HDD_WORKERS * $(bytes_for_gib "${HDD_BYTES%G}")))
ensure_capacity_budget "$TOTAL_BYTES" "$AVAILABLE_BYTES" "$WORKSET_BYTES"

case "$DISK_PROFILE" in
    nvme*) FIO_PERFORMANCE_IODEPTH=32 ;;
    ssd*) FIO_PERFORMANCE_IODEPTH=16 ;;
    *) FIO_PERFORMANCE_IODEPTH=4 ;;
esac
PERFORMANCE_DURATION=$DURATION
FIO_PERFORMANCE_TOTAL_QD=$((HDD_WORKERS * FIO_PERFORMANCE_IODEPTH))

if [ "$DURATION" -le 180 ]; then
    FIO_DURABILITY_BYTES="8M"
    FIO_DURABILITY_PROFILE="<= 3 minutes"
elif [ "$DURATION" -le 3600 ]; then
    FIO_DURABILITY_BYTES="32M"
    FIO_DURABILITY_PROFILE="3-60 minutes"
else
    FIO_DURABILITY_BYTES="256M"
    FIO_DURABILITY_PROFILE="> 60 minutes"
fi

DISK_MODEL=$(cat /sys/block/${DISK_DEV}/device/model 2>/dev/null | xargs || true)
if [ -z "$DISK_MODEL" ] || [ "$DISK_MODEL" = "Unknown" ]; then
    DISK_MODEL_LINE=""
else
    DISK_MODEL_LINE="磁盘型号              : ${DISK_MODEL}"
fi

DISK_SIZE=$(lsblk -dn -o SIZE "/dev/${DISK_DEV}" 2>/dev/null | xargs || echo "Unknown")
OS_INFO=$(cat /etc/os-release 2>/dev/null | awk -F= '/^PRETTY_NAME=/ {gsub(/"/,"",$2); print $2}')

echo "======================================"
echo "Disk Random Mixed I/O Stability Test Start"
echo "Test Dir    : ${TEST_DIR}"
echo "Mount Point : ${MOUNT_POINT}"
echo "Device      : /dev/${DISK_DEV}"
echo "Storage Profile : ${DISK_PROFILE} (rota=${DISK_ROTA:-unknown}, transport=${DISK_TRAN:-unknown}, auto=${AUTO_PROFILE})"
echo "Filesystem  : ${FS_TYPE}"
echo "Workers     : ${HDD_WORKERS}"
echo "Worker Data : ${HDD_BYTES}"
echo "Safety Reserve : ${SAFETY_RESERVE_BYTES} bytes"
echo "I/O Path    : ${FIO_PATH}"
echo "Duration    : ${DURATION}"
echo "Interval    : ${INTERVAL}s"
echo "Mode        : fio 4K random mixed I/O (read 30% / write 70%)"
echo "======================================"

(
echo "timestamp,used_GB,avail_GB,use_percent,read_MBps,read_iops,read_await_ms,write_MBps,write_iops,write_await_ms,util_percent"

PREV_LINE=$(awk -v dev="$DISK_DEV" '$3==dev {print}' /proc/diskstats)
PREV_TIME=$(date +%s)

while true; do
    TS=$(date '+%F %T')
    DF_LINE=$(df -BG "$TEST_DIR" | awk 'NR==2 {gsub("G","",$3); gsub("G","",$4); gsub("%","",$5); print $3","$4","$5}')

    CUR_LINE=$(awk -v dev="$DISK_DEV" '$3==dev {print}' /proc/diskstats)
    CUR_TIME=$(date +%s)
    DT=$((CUR_TIME - PREV_TIME))
    [ "$DT" -le 0 ] && DT=1

    if [ -n "$PREV_LINE" ] && [ -n "$CUR_LINE" ]; then
        METRICS=$(awk -v p="$PREV_LINE" -v c="$CUR_LINE" -v dt="$DT" '
        BEGIN {
            split(p,a," ");
            split(c,b," ");

            r_ios=b[4]-a[4];
            r_sec=b[6]-a[6];
            r_ticks=b[7]-a[7];
            w_ios=b[8]-a[8];
            w_sec=b[10]-a[10];
            w_ticks=b[11]-a[11];
            io_ticks=b[13]-a[13];

            write_MBps=(w_sec*512/1024/1024)/dt;
            write_iops=w_ios/dt;

            read_MBps=(r_sec*512/1024/1024)/dt;
            read_iops=r_ios/dt;
            read_await=(r_ios>0 ? r_ticks/r_ios : 0);
            write_await=(w_ios>0 ? w_ticks/w_ios : 0);
            if (read_await < 0 || read_await > 5000) read_await="";
            if (write_await < 0 || write_await > 5000) write_await="";

            util=io_ticks/(dt*10);
            if (util>100) util=100;

            printf "%.2f,%.2f,%s,%.2f,%.2f,%s,%.2f", read_MBps,read_iops,read_await,write_MBps,write_iops,write_await,util
        }')
    else
        METRICS="0,0,0,0,0,0,0"
    fi

    echo "$TS,$DF_LINE,$METRICS"

    PREV_LINE="$CUR_LINE"
    PREV_TIME="$CUR_TIME"
    sleep "$INTERVAL"
done
) > "$MON_LOG" &

MON_PID=$!

dmesg -w | egrep -i "$CRITICAL_ERR_PATTERN" > "$ERR_LOG" &
ERR_PID=$!

sleep 2

set +e

echo "[STAGE] stress_start"
(
  cd "$TEST_DIR" || exit 1

  echo "===== fio disk test start ====="
  echo "Start Time : $(date '+%F %T')"
  echo "Test Dir   : ${TEST_DIR}"
  echo "Workers    : ${HDD_WORKERS}"
  echo "Performance Duration : ${PERFORMANCE_DURATION}"
  echo "Durability Mode      : fixed-size write and CRC32C verify"
  echo "Mode       : ${FIO_PATH}"
  echo

  echo "===== fio performance test start ====="
  stdbuf -oL -eL fio \
    --name=hpcdeploy-performance \
    --directory="${TEST_DIR}" \
    --rw="${FIO_RW}" \
    --rwmixwrite="${FIO_RWMIXWRITE}" \
    --bs="${FIO_BS}" \
    --numjobs="${HDD_WORKERS}" \
    --size="${HDD_BYTES}" \
    --ioengine="${FIO_PERFORMANCE_IOENGINE}" \
    --iodepth="${FIO_PERFORMANCE_IODEPTH}" \
    --direct=1 \
    --clat_percentiles=1 \
    --percentile_list=95:99 \
    --time_based=1 \
    --runtime="${PERFORMANCE_DURATION}" \
    --group_reporting=1 \
    --unlink=1 \
    --eta=never \
    --output-format=json \
    --output="${FIO_JSON}"

  PERFORMANCE_RET=$?
  echo "Performance Exit Code : ${PERFORMANCE_RET}"
  echo "===== fio performance test end ====="

  echo "===== fio durability test start ====="
  stdbuf -oL -eL fio \
    --name=hpcdeploy-durability \
    --directory="${TEST_DIR}" \
    --rw=randwrite \
    --bs="${FIO_BS}" \
    --numjobs="${HDD_WORKERS}" \
    --size="${FIO_DURABILITY_BYTES}" \
    --ioengine=psync \
    --direct=1 \
    --fdatasync=1 \
    --verify="${FIO_VERIFY}" \
    --verify_fatal=1 \
    --do_verify=1 \
    --clat_percentiles=1 \
    --percentile_list=95:99 \
    --group_reporting=1 \
    --unlink=1 \
    --eta=never \
    --output-format=json \
    --output="${FIO_DURABILITY_JSON}"

  DURABILITY_RET=$?
  RET=0
  [ "$PERFORMANCE_RET" -ne 0 ] && RET="$PERFORMANCE_RET"
  [ "$DURABILITY_RET" -ne 0 ] && RET="$DURABILITY_RET"

  echo
  echo "End Time   : $(date '+%F %T')"
  echo "Exit Code  : ${RET}"
  echo "===== fio disk test end ====="

  exit ${RET}
) > "$STRESS_LOG" 2>&1 &

STRESS_PID=$!

STRESS_START=$(date +%s)
BAR_WIDTH=50

while kill -0 "$STRESS_PID" 2>/dev/null; do
    CUR_TIME=$(date +%s)
    ELAPSED=$((CUR_TIME - STRESS_START))
    [ "$ELAPSED" -gt "$DURATION" ] && ELAPSED=$DURATION

    PERCENT=$((ELAPSED * 100 / DURATION))
    FILLED=$((PERCENT * BAR_WIDTH / 100))
    EMPTY=$((BAR_WIDTH - FILLED))

    printf "\r[%-50s] %3d%% (Elapsed: %3ds / %ds)" \
      "$(printf '#%.0s' $(seq 1 $FILLED))$(printf ' %.0s' $(seq 1 $EMPTY))" \
      "$PERCENT" "$ELAPSED" "$DURATION"

    sleep "$INTERVAL"
done

wait "$STRESS_PID"
STRESS_EXIT=$?

printf "\r[%-50s] 100%% (Elapsed: %3ds / %ds)\n" \
  "$(printf '#%.0s' $(seq 1 $BAR_WIDTH))" "$DURATION" "$DURATION"

set -e

kill "$MON_PID" >/dev/null 2>&1 || true
kill "$ERR_PID" >/dev/null 2>&1 || true
sleep 1

FIO_METRICS_ENV="${WORKDIR}/fio_metrics_${TIME_TAG}.env"
python3 - "$FIO_JSON" > "$FIO_METRICS_ENV" <<'PYEOF'
import json
import sys

defaults = {
    "FIO_METRICS_STATUS": "invalid_json",
    "FIO_READ_BW_MBPS": "0.00", "FIO_READ_IOPS": "0.00",
    "FIO_READ_CLAT_MEAN_MS": "0.000", "FIO_READ_CLAT_P95_MS": "0.000", "FIO_READ_CLAT_P99_MS": "0.000",
    "FIO_WRITE_BW_MBPS": "0.00", "FIO_WRITE_IOPS": "0.00",
    "FIO_WRITE_CLAT_MEAN_MS": "0.000", "FIO_WRITE_CLAT_P95_MS": "0.000", "FIO_WRITE_CLAT_P99_MS": "0.000",
}

def latency_ms(stats, field):
    for unit, scale in (("clat_ns", 1_000_000), ("clat_us", 1_000), ("clat_ms", 1)):
        values = stats.get(unit) or {}
        if field == "mean":
            return float(values.get("mean", 0)) / scale
        percentiles = values.get("percentile") or {}
        return float(percentiles.get(field, 0)) / scale
    return 0.0

try:
    with open(sys.argv[1], encoding="utf-8") as f:
        json_text = f.read()
    if "{" not in json_text:
        raise ValueError("fio JSON payload is missing")
    job = json.loads(json_text[json_text.find("{"):])["jobs"][0]
    for direction, prefix in (("read", "FIO_READ"), ("write", "FIO_WRITE")):
        stats = job.get(direction) or {}
        defaults[f"{prefix}_BW_MBPS"] = f"{float(stats.get('bw_bytes', 0)) / 1024 / 1024:.2f}"
        defaults[f"{prefix}_IOPS"] = f"{float(stats.get('iops', 0)):.2f}"
        defaults[f"{prefix}_CLAT_MEAN_MS"] = f"{latency_ms(stats, 'mean'):.3f}"
        defaults[f"{prefix}_CLAT_P95_MS"] = f"{latency_ms(stats, '95.000000'):.3f}"
        defaults[f"{prefix}_CLAT_P99_MS"] = f"{latency_ms(stats, '99.000000'):.3f}"
    defaults["FIO_METRICS_STATUS"] = "ok"
except (FileNotFoundError, IndexError, KeyError, ValueError, json.JSONDecodeError):
    pass

for key, value in defaults.items():
    print(f"{key}={value}")
PYEOF
. "$FIO_METRICS_ENV"

FIO_DURABILITY_METRICS_ENV="${WORKDIR}/fio_durability_metrics_${TIME_TAG}.env"
python3 - "$FIO_DURABILITY_JSON" > "$FIO_DURABILITY_METRICS_ENV" <<'PYEOF'
import json
import sys

metrics = {
    "FIO_DURABILITY_STATUS": "invalid_json",
    "FIO_DURABILITY_WRITE_IOPS": "0.00",
    "FIO_DURABILITY_SYNC_MEAN_MS": "0.000",
    "FIO_DURABILITY_SYNC_P95_MS": "0.000",
    "FIO_DURABILITY_SYNC_P99_MS": "0.000",
}

try:
    json_text = open(sys.argv[1], encoding="utf-8").read()
    if "{" not in json_text:
        raise ValueError("fio JSON payload is missing")
    job = json.loads(json_text[json_text.find("{"):])["jobs"][0]
    sync = (job.get("sync") or {}).get("lat_ns") or {}
    percentiles = sync.get("percentile") or {}
    metrics["FIO_DURABILITY_WRITE_IOPS"] = f"{float((job.get('write') or {}).get('iops', 0)):.2f}"
    metrics["FIO_DURABILITY_SYNC_MEAN_MS"] = f"{float(sync.get('mean', 0)) / 1_000_000:.3f}"
    metrics["FIO_DURABILITY_SYNC_P95_MS"] = f"{float(percentiles.get('95.000000', 0)) / 1_000_000:.3f}"
    metrics["FIO_DURABILITY_SYNC_P99_MS"] = f"{float(percentiles.get('99.000000', 0)) / 1_000_000:.3f}"
    metrics["FIO_DURABILITY_STATUS"] = "ok"
except (FileNotFoundError, IndexError, KeyError, ValueError, json.JSONDecodeError):
    pass

for key, value in metrics.items():
    print(f"{key}={value}")
PYEOF
. "$FIO_DURABILITY_METRICS_ENV"

USED_MAX=$(awk -F',' 'NR>1 {if($2>max)max=$2} END{print max+0}' "$MON_LOG")
AVAIL_MIN=$(awk -F',' 'NR>1 {if(NR==2 || $3<min)min=$3} END{print min+0}' "$MON_LOG")
USE_MAX=$(awk -F',' 'NR>1 {if($4>max)max=$4} END{print max+0}' "$MON_LOG")

UTIL_AVG=$(awk -F',' 'NR>1 {sum+=$11; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
UTIL_MAX=$(awk -F',' 'NR>1 {if($11>max)max=$11} END{printf "%.2f",max+0}' "$MON_LOG")

ERROR_COUNT=$(grep -Ei "$CRITICAL_ERR_PATTERN" "$ERR_LOG" | wc -l)
STRESS_ERROR=$(grep -Ei "verify.*(fail|error)|verification failed|aborted|segmentation fault|bus error|input/output error|read error|write error|fio:.*(fail|error)" "$STRESS_LOG" || true)

RESULT="PASS"
REASON="No critical error detected."

if [ "$STRESS_EXIT" != "0" ]; then
    RESULT="FAIL"
    REASON="fio exited abnormally. Exit code: ${STRESS_EXIT}"
fi

if [ "$FIO_METRICS_STATUS" != "ok" ]; then
    RESULT="FAIL"
    REASON="fio JSON result is missing or invalid."
fi

if [ "$FIO_DURABILITY_STATUS" != "ok" ]; then
    RESULT="FAIL"
    REASON="fio durability JSON result is missing or invalid."
fi

if [ "$ERROR_COUNT" != "0" ]; then
    RESULT="FAIL"
    REASON="Critical kernel disk error detected."
fi

if [ -n "$STRESS_ERROR" ]; then
    RESULT="FAIL"
    REASON="fio reported a data verification or I/O error."
fi

cat > "$REPORT" << EOR
磁盘随机混合读写稳定性压力测试报告

一、测试对象
操作系统              : ${OS_INFO}
测试目录              : ${TEST_DIR}
挂载点                : ${MOUNT_POINT}
挂载源                : ${MOUNT_SRC}
磁盘设备              : /dev/${DISK_DEV}
${DISK_MODEL_LINE}
磁盘容量              : ${DISK_SIZE}
文件系统              : ${FS_TYPE}
Storage Profile       : ${DISK_PROFILE}
设备旋转属性          : ${DISK_ROTA:-unknown}
设备传输链路          : ${DISK_TRAN:-unknown}
自动定档              : ${AUTO_PROFILE}
安全余量              : ${SAFETY_RESERVE_BYTES} bytes
I/O Path              : ${FIO_PATH}

二、测试方法
测试工具              : fio
fio并发任务数         : ${HDD_WORKERS}
线程计算方式          : 自动按 HDD / SSD / NVMe 定档；WORKERS 可显式覆盖
性能主测模式          : ${FIO_PATH}
性能主测时长          : ${PERFORMANCE_DURATION} 秒
性能主测队列深度      : ${FIO_PERFORMANCE_IODEPTH}
性能主测总队列深度    : ${FIO_PERFORMANCE_TOTAL_QD}
持久化校验模式        : 固定工作集完整写入后 CRC32C 回读
持久化校验工作集      : ${FIO_DURABILITY_BYTES} / worker
持久化工作集分档      : ${FIO_DURABILITY_PROFILE}
单Worker数据量        : ${HDD_BYTES}
总工作集上限          : ${WORKSET_BYTES} bytes
测试类型              : 性能主测：4K 随机混合读写（读 30% / 写 70%）；持久化：4K 随机写
数据校验              : 持久化阶段 ${FIO_VERIFY}，完成负载后校验
测试时长              : ${DURATION}
采样间隔              : ${INTERVAL} 秒
测试目录              : ${TEST_DIR}

三、测试结果统计
最高已用空间          : ${USED_MAX} GB
最低可用空间          : ${AVAIL_MIN} GB
最高使用率            : ${USE_MAX} %

性能主测读取带宽      : ${FIO_READ_BW_MBPS} MB/s
性能主测读取IOPS      : ${FIO_READ_IOPS}
性能主测读取平均延迟  : ${FIO_READ_CLAT_MEAN_MS} ms
性能主测读取p95延迟   : ${FIO_READ_CLAT_P95_MS} ms
性能主测读取p99延迟   : ${FIO_READ_CLAT_P99_MS} ms

性能主测写入带宽      : ${FIO_WRITE_BW_MBPS} MB/s
性能主测写入IOPS      : ${FIO_WRITE_IOPS}
性能主测写入平均延迟  : ${FIO_WRITE_CLAT_MEAN_MS} ms
性能主测写入p95延迟   : ${FIO_WRITE_CLAT_P95_MS} ms
性能主测写入p99延迟   : ${FIO_WRITE_CLAT_P99_MS} ms

持久化校验写IOPS      : ${FIO_DURABILITY_WRITE_IOPS}
持久化同步平均延迟    : ${FIO_DURABILITY_SYNC_MEAN_MS} ms
持久化同步p95延迟     : ${FIO_DURABILITY_SYNC_P95_MS} ms
持久化同步p99延迟     : ${FIO_DURABILITY_SYNC_P99_MS} ms

平均util              : ${UTIL_AVG} %
最大util              : ${UTIL_MAX} %


四、异常检查
fio退出码             : ${STRESS_EXIT}
重大内核磁盘异常数量  : ${ERROR_COUNT}
fio严重错误            : $( [ -z "$STRESS_ERROR" ] && echo "未发现" || echo "发现严重错误，请查看 ${STRESS_LOG}" )

五、综合判定
测试结果              : ${RESULT}
判定原因              : ${REASON}

六、结论
$(if [ "$RESULT" = "PASS" ]; then
cat << PASS_TEXT
本次磁盘随机混合读写稳定性压力测试期间，指定目录所在磁盘完成 4K 随机混合读写性能主测，以及固定工作集的 CRC32C 回读校验；未发现 fio 校验错误、I/O 错误、NVMe 控制器异常或文件系统重大错误。

综合判断：本次测试通过，磁盘在持续随机混合读写负载下运行稳定，未发现数据校验失败、文件系统异常或内核级磁盘故障。

PASS_TEXT
else
cat << FAIL_TEXT
本次磁盘随机混合读写稳定性压力测试未通过。建议结合 fio 日志、磁盘监控日志、dmesg 日志、SMART/NVMe 健康状态进一步排查。
FAIL_TEXT
fi)

七、原始文件
fio日志                : ${STRESS_LOG}
fio性能JSON结果        : ${FIO_JSON}
fio持久化JSON结果      : ${FIO_DURABILITY_JSON}
资源监控日志          : ${MON_LOG}
内核错误日志          : ${ERR_LOG}
Excel报告             : ${XLSX_REPORT}

八、报告生成信息
报告生成时间          : $(date "+%F %T")
EOR

python3 - << PYEOF
import csv
import math
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

report = Path("${REPORT}")
stress_log = Path("${STRESS_LOG}")
fio_json = Path("${FIO_JSON}")
fio_durability_json = Path("${FIO_DURABILITY_JSON}")
mon_log = Path("${MON_LOG}")
err_log = Path("${ERR_LOG}")
xlsx = Path("${XLSX_REPORT}")

result = "${RESULT}"
reason = "${REASON}"

def clean_excel_text(v):
    if v is None:
        return ""
    s = ILLEGAL_CHARACTERS_RE.sub("", str(v))
    if s.startswith(("=", "+", "-", "@")):
        s = "'" + s
    return s

def to_number(v):
    try:
        x = float(str(v).strip())
        if math.isnan(x) or math.isinf(x):
            return 0
        return x
    except Exception:
        return 0

wb = Workbook()
ws = wb.active
ws.title = "Summary"
raw = wb.create_sheet("RawReport")
stress = wb.create_sheet("StressLog")
fio_raw = wb.create_sheet("FioJSON")
fio_durability_raw = wb.create_sheet("FioDurabilityJSON")
mon = wb.create_sheet("MonitorCSV")
err = wb.create_sheet("KernelError")

dark = "1F4E78"
green = "C6EFCE"
red = "FFC7CE"
gray = "F2F2F2"
white = "FFFFFF"

border = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9")
)

ws.merge_cells("A1:H1")
ws["A1"] = "磁盘随机混合读写稳定性压力测试报告"
ws["A1"].font = Font(size=18, bold=True, color=white)
ws["A1"].fill = PatternFill("solid", fgColor=dark)
ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[1].height = 30

def section(row, title):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    c = ws.cell(row=row, column=1, value=title)
    c.font = Font(bold=True, color=white)
    c.fill = PatternFill("solid", fgColor=dark)
    return row + 1

def kv(row, key, value):
    ws.cell(row=row, column=1, value=clean_excel_text(key))
    ws.cell(row=row, column=2, value=clean_excel_text(value))
    for col in range(1, 3):
        cell = ws.cell(row=row, column=col)
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=gray)
    ws.cell(row=row, column=1).font = Font(bold=True)
    return row + 1

r = 3
r = section(r, "一、测试对象")
test_object_rows = [
    ("操作系统", "${OS_INFO}"),
    ("测试目录", "${TEST_DIR}"),
    ("挂载点", "${MOUNT_POINT}"),
    ("挂载源", "${MOUNT_SRC}"),
    ("磁盘设备", "/dev/${DISK_DEV}"),
]
if "${DISK_MODEL}".strip():
    test_object_rows.append(("磁盘型号", "${DISK_MODEL}"))
test_object_rows.extend([
    ("磁盘容量", "${DISK_SIZE}"),
    ("文件系统", "${FS_TYPE}"),
    ("Storage Profile", "${DISK_PROFILE}"),
    ("设备旋转属性", "${DISK_ROTA:-unknown}"),
    ("设备传输链路", "${DISK_TRAN:-unknown}"),
    ("自动定档", "${AUTO_PROFILE}"),
    ("Safety Reserve", "${SAFETY_RESERVE_BYTES} bytes"),
    ("I/O Path", "${FIO_PATH}"),
])
for k, v in test_object_rows:
    r = kv(r, k, v)

r += 1
r = section(r, "二、测试方法")
for k, v in [
    ("测试工具", "fio"),
    ("fio并发任务数", "${HDD_WORKERS}"),
    ("线程计算方式", "自动按 HDD / SSD / NVMe 定档；WORKERS 可显式覆盖"),
    ("性能主测模式", "${FIO_PATH}"),
    ("性能主测时长", "${PERFORMANCE_DURATION} 秒"),
    ("性能主测队列深度", "${FIO_PERFORMANCE_IODEPTH}"),
    ("性能主测总队列深度", "${FIO_PERFORMANCE_TOTAL_QD}"),
    ("持久化校验模式", "固定工作集完整写入后 CRC32C 回读"),
    ("持久化校验工作集", "${FIO_DURABILITY_BYTES} / worker"),
    ("持久化工作集分档", "${FIO_DURABILITY_PROFILE}"),
    ("单Worker数据量", "${HDD_BYTES}"),
    ("总工作集上限", "${WORKSET_BYTES} bytes"),
    ("测试类型", "性能主测：4K 随机混合读写（读 30% / 写 70%）；持久化：4K 随机写"),
    ("数据校验", "持久化阶段 ${FIO_VERIFY}，完成负载后校验"),
    ("测试时长", "${DURATION}"),
    ("采样间隔", "${INTERVAL} 秒"),
]:
    r = kv(r, k, v)


r += 1
r = section(r, "三、测试结果统计")

headers = ["类别", "指标", "数值"]
for i, h in enumerate(headers, 1):
    cell = ws.cell(row=r, column=i, value=clean_excel_text(h))
    cell.font = Font(bold=True, color=white)
    cell.fill = PatternFill("solid", fgColor=dark)
    cell.border = border
r += 1

rows = [
    ("磁盘空间", "最高已用空间", "${USED_MAX} GB"),
    ("磁盘空间", "最低可用空间", "${AVAIL_MIN} GB"),
    ("磁盘空间", "最高使用率", "${USE_MAX} %"),

    ("性能主测", "读取带宽", "${FIO_READ_BW_MBPS} MB/s"),
    ("性能主测", "读取IOPS", "${FIO_READ_IOPS}"),
    ("性能主测", "读取平均延迟", "${FIO_READ_CLAT_MEAN_MS} ms"),
    ("性能主测", "读取p95/p99延迟", "${FIO_READ_CLAT_P95_MS} / ${FIO_READ_CLAT_P99_MS} ms"),
    ("性能主测", "写入带宽", "${FIO_WRITE_BW_MBPS} MB/s"),
    ("性能主测", "写入IOPS", "${FIO_WRITE_IOPS}"),
    ("性能主测", "写入平均延迟", "${FIO_WRITE_CLAT_MEAN_MS} ms"),
    ("性能主测", "写入p95/p99延迟", "${FIO_WRITE_CLAT_P95_MS} / ${FIO_WRITE_CLAT_P99_MS} ms"),
    ("持久化校验", "写IOPS", "${FIO_DURABILITY_WRITE_IOPS}"),
    ("持久化校验", "同步p95/p99延迟", "${FIO_DURABILITY_SYNC_P95_MS} / ${FIO_DURABILITY_SYNC_P99_MS} ms"),
    ("运行状态", "平均util", "${UTIL_AVG} %"),
    ("运行状态", "最大util", "${UTIL_MAX} %"),

    ("异常检查", "fio退出码", "${STRESS_EXIT}"),
    ("异常检查", "重大内核磁盘异常数量", "${ERROR_COUNT}"),
]


for row in rows:
    for c, v in enumerate(row, 1):
        cell = ws.cell(row=r, column=c, value=clean_excel_text(v))
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    r += 1

r += 1
r = section(r, "四、综合判定")
r = kv(r, "测试结果", result)
ws.cell(row=r-1, column=2).fill = PatternFill("solid", fgColor=green if result == "PASS" else red)
ws.cell(row=r-1, column=2).font = Font(bold=True)
r = kv(r, "判定原因", reason)
r = kv(r, "报告生成时间", "$(date "+%F %T")")

for col, width in {"A":18, "B":38, "C":22, "D":14, "E":14, "F":14, "G":14, "H":14}.items():
    ws.column_dimensions[col].width = width

if report.exists():
    for line in report.read_text(errors="ignore").splitlines():
        raw.append([clean_excel_text(line)])
raw.column_dimensions["A"].width = 120

if stress_log.exists():
    for line in stress_log.read_text(errors="ignore").splitlines():
        stress.append([clean_excel_text(line)])
stress.column_dimensions["A"].width = 120

if fio_json.exists():
    for line in fio_json.read_text(errors="ignore").splitlines():
        fio_raw.append([clean_excel_text(line)])
fio_raw.column_dimensions["A"].width = 120

if fio_durability_json.exists():
    for line in fio_durability_json.read_text(errors="ignore").splitlines():
        fio_durability_raw.append([clean_excel_text(line)])
fio_durability_raw.column_dimensions["A"].width = 120

if err_log.exists() and err_log.stat().st_size > 0:
    for line in err_log.read_text(errors="ignore").splitlines():
        err.append([clean_excel_text(line)])
else:
    err.append([clean_excel_text("No critical disk error detected.")])
err.column_dimensions["A"].width = 120

if mon_log.exists():
    with mon_log.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader, 1):
            out = []
            for j, val in enumerate(row, 1):
                if idx > 1 and j >= 2:
                    if j in {7, 10}:
                        s = str(val).strip()
                        if s == "":
                            out.append(None)
                        else:
                            v = to_number(s)
                            if v < 0 or v > 5000:
                                out.append(None)
                            else:
                                out.append(v)
                    else:
                        out.append(to_number(val))
                else:
                    out.append(clean_excel_text(val.strip()) if isinstance(val, str) else val)
            mon.append(out)

for sheet in [raw, stress, fio_raw, fio_durability_raw, mon, err]:
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=dark)

for col in range(1, mon.max_column + 1):
    mon.column_dimensions[get_column_letter(col)].width = 22

if mon.max_row > 2 and mon.max_column >= 11:
    def add_chart(title, col, pos):
        chart = LineChart()
        chart.title = title
        chart.y_axis.title = title
        chart.x_axis.title = "Sample"
        data = Reference(mon, min_col=col, min_row=1, max_row=mon.max_row)
        chart.add_data(data, titles_from_data=True)
        chart.height = 7
        chart.width = 14
        ws.add_chart(chart, pos)

    add_chart("读取速度变化趋势(MB/s)", 5, "J3")
    add_chart("写入速度变化趋势(MB/s)", 8, "J18")
    add_chart("读取延迟变化趋势(ms)", 7, "J33")
    add_chart("写入延迟变化趋势(ms)", 10, "J48")
    add_chart("磁盘util变化趋势(%)", 11, "J63")


for sheet in wb.worksheets:
    for row in sheet.iter_rows():
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(wrap_text=True, vertical="center")

wb.save(xlsx)
print(f"XLSX Report : {xlsx}")
PYEOF

echo
echo "======================================"
echo "Disk Random Mixed I/O Stability Test Finished"
echo "Result       : ${RESULT}"
echo "Reason       : ${REASON}"
echo "Test Dir     : ${TEST_DIR}"
echo "Device       : /dev/${DISK_DEV}"
echo "Stress Log   : ${STRESS_LOG}"
echo "Monitor CSV  : ${MON_LOG}"
echo "Kernel Error : ${ERR_LOG}"
echo "Text Report  : ${REPORT}"
echo "XLSX Report  : ${XLSX_REPORT}"
echo "======================================"
