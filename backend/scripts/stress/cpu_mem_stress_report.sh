#!/bin/bash
#set -e  # 不使用 set -e，手工控制每个关键步骤的退出处理

# ===== 自动检测系统并安装依赖 =====
echo "[STAGE] dependency_check_start"

install_deps() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "[ERROR] 请使用 root 用户运行，或使用 sudo"
        exit 1
    fi

    NEED_INSTALL=0

    if ! command -v stress-ng >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        NEED_INSTALL=1
    else
        if ! python3 - << 'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            NEED_INSTALL=1
        fi
    fi

    if [ "$NEED_INSTALL" -eq 0 ]; then
        echo "[INFO] Dependencies already installed, skip install."
        return 0
    fi

    echo "[INFO] Missing dependencies detected, installing..."

    if [ -f /etc/redhat-release ]; then
        echo "[INFO] Detected RHEL/CentOS/Rocky/Alma"

        yum install -y epel-release || true
        yum install -y stress-ng python3 python3-pip python3-openpyxl || true

        if ! python3 - << 'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    elif [ -f /etc/debian_version ]; then
        echo "[INFO] Detected Debian/Ubuntu"

        apt update
        apt install -y stress-ng python3 python3-pip python3-openpyxl

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

install_deps
echo "[STAGE] dependency_check_done"

DURATION=${1:-43200}
INTERVAL=${2:-2}
TIME_TAG=$(date +%F_%H%M%S)
WORKDIR=$(pwd)
STOP_FILE="${WORKDIR}/.monitor.stop"
rm -f "$STOP_FILE"

STRESS_LOG="${WORKDIR}/stress_cpu_mem_${TIME_TAG}.log"
MON_LOG="${WORKDIR}/cpu_mem_monitor_${TIME_TAG}.csv"
ERR_LOG="${WORKDIR}/cpu_mem_error_${TIME_TAG}.log"
REPORT="${WORKDIR}/cpu_mem_report_${TIME_TAG}.txt"
XLSX_REPORT="${WORKDIR}/cpu_mem_report_${TIME_TAG}.xlsx"

CPU_WORKERS=${WORKERS:-$(nproc)}
CPU_CORES=$(nproc)

VM_WORKERS=$(( CPU_WORKERS / 8 ))
[ "$VM_WORKERS" -lt 1 ] && VM_WORKERS=1

VM_BYTES="${MEMORY_PERCENT:-85}%"

CRITICAL_ERR_PATTERN="out of memory|oom-killer|killed process|hardware error|machine check error|machine check exception|mce:.*error|edac.*error|ecc.*uncorrected|uncorrected error|thermal thrott|throttling|segfault|general protection fault|verification failed"

command -v stress-ng >/dev/null || { echo "ERROR: stress-ng not found"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }

python3 - << 'PYCHK'
try:
    import openpyxl
except Exception:
    raise SystemExit("ERROR: python3-openpyxl not found. Install: apt install -y python3-openpyxl 或 yum install -y python3-openpyxl")
PYCHK

CPU_MODEL=$(lscpu | awk -F: '/Model name/ {gsub(/^ +/,"",$2); print $2; exit}')
MEM_TOTAL=$(free -h | awk '/Mem:/ {print $2}')
OS_INFO=$(cat /etc/os-release 2>/dev/null | awk -F= '/^PRETTY_NAME=/ {gsub(/"/,"",$2); print $2}')

# Swap 阈值：默认 1024 MB，swap 占用过多视为系统异常
SWAP_FAIL_MB=${SWAP_FAIL_MB:-1024}
SWAP_TOTAL=$(free -m | awk '/Swap:/ {print $2}')
# 若系统总 swap 小于阈值则自动降低（避免小 swap 系统误报）
if [ "$SWAP_TOTAL" -lt "$SWAP_FAIL_MB" ] 2>/dev/null; then
    SWAP_FAIL_MB=$(( SWAP_TOTAL * 80 / 100 ))
fi

echo "======================================"
echo "CPU + Memory Stress Test Start"
echo "CPU Workers : ${CPU_WORKERS}"
echo "VM Workers  : ${VM_WORKERS}"
echo "VM Bytes    : ${VM_BYTES}"
echo "Duration    : ${DURATION}s"
echo "Interval    : ${INTERVAL}s"
echo "Workdir     : ${WORKDIR}"
echo "======================================"

# ===== 统一的 cleanup 陷阱 =====
# 确保脚本在任何退出路径下都能清理后台进程
# 递归 kill 进程树（先子后父），用于无独立进程组时的精确清理
_kill_tree() {
  local _kt_pid="$1"
  local _kt_sig="$2"
  [ -z "$_kt_pid" ] && return
  for _kt_child in $(pgrep -P "$_kt_pid" 2>/dev/null || true); do
    _kill_tree "$_kt_child" "$_kt_sig"
  done
  kill "-$_kt_sig" "$_kt_pid" 2>/dev/null || true
}

# 等待指定 PID 退出，避免使用 `timeout wait` 这种不可靠写法
_wait_pid_with_timeout() {
  local _wp_pid="$1"
  local _wp_seconds="${2:-5}"
  local _wp_i=0

  [ -z "$_wp_pid" ] && return 0

  while kill -0 "$_wp_pid" 2>/dev/null && [ "$_wp_i" -lt "$_wp_seconds" ]; do
    sleep 1
    _wp_i=$(( _wp_i + 1 ))
  done

  # 进程已退出时回收；仍未退出时不阻塞主脚本
  if ! kill -0 "$_wp_pid" 2>/dev/null; then
    wait "$_wp_pid" 2>/dev/null || true
  fi
}

# 清理独立进程组；PGID 安全校验，避免误杀当前脚本
_kill_process_group() {
  local _kg_pgid="$1"
  local _kg_sig="$2"
  [ -z "$_kg_pgid" ] && return 0
  [ "$_kg_pgid" = "0" ] && return 0
  [ "$_kg_pgid" = "$$" ] && return 0
  kill "-$_kg_sig" "$_kg_pgid" 2>/dev/null || true
}
_CLEANUP_RAN=0
_cleanup() {
    [ "$_CLEANUP_RAN" = "1" ] && return
    _CLEANUP_RAN=1

    # 通知监控循环退出
    touch "$STOP_FILE" 2>/dev/null || true

    # 关闭资源监控进程
    if [ -n "${MON_PID:-}" ]; then
        kill "$MON_PID" 2>/dev/null || true
        _wait_pid_with_timeout "$MON_PID" 3
    fi

    # 关闭 dmesg 监控进程组
    if [ -n "${ERR_PGID:-}" ]; then
        _kill_process_group "$ERR_PGID" TERM
    elif [ -n "${ERR_PID:-}" ]; then
        _kill_tree "$ERR_PID" TERM
    fi
    [ -n "${ERR_PID:-}" ] && _wait_pid_with_timeout "$ERR_PID" 3

    # 清理子进程
    pkill -P $$ dmesg 2>/dev/null || true
    pkill -P $$ grep 2>/dev/null || true

    # 清理 stress-ng 进程组（setsid 启动，非 $$ 子进程，需单独处理）
    if [ -n "${STRESS_PGID:-}" ] && [ "${STRESS_PGID:-}" != "0" ] && [ "${STRESS_PGID:-}" != "$$" ]; then
      _kill_process_group "$STRESS_PGID" TERM
      _wait_pid_with_timeout "${STRESS_PID:-}" 3
      kill -0 "${STRESS_PID:-}" 2>/dev/null && _kill_process_group "$STRESS_PGID" KILL
    elif [ -n "${STRESS_PID:-}" ]; then
      # 无独立进程组，递归杀进程树
      _kill_tree "$STRESS_PID" TERM
      sleep 2
      kill -0 "$STRESS_PID" 2>/dev/null && _kill_tree "$STRESS_PID" KILL
    fi
    if [ -n "${TAIL_PID:-}" ]; then
      kill "$TAIL_PID" 2>/dev/null || true
    fi
    pkill -P $$ tee 2>/dev/null || true
}
trap _cleanup EXIT

# ===== 启动后台监控 =====
echo "[STAGE] monitor_start"

(
echo "timestamp,load1,load5,load15,mem_total_MB,mem_used_MB,mem_free_MB,mem_available_MB,swap_total_MB,swap_used_MB"
while [ ! -f "$STOP_FILE" ]; do
    TS=$(date '+%F %T')
    LOAD=$(uptime | awk -F'load average:' '{print $2}' | sed 's/,//g')
    LOAD1=$(echo "$LOAD" | awk '{print $1}')
    LOAD5=$(echo "$LOAD" | awk '{print $2}')
    LOAD15=$(echo "$LOAD" | awk '{print $3}')
    MEM_LINE=$(free -m | awk '/Mem:/ {print $2","$3","$4","$7}')
    SWAP_LINE=$(free -m | awk '/Swap:/ {print $2","$3}')
    echo "$TS,$LOAD1,$LOAD5,$LOAD15,$MEM_LINE,$SWAP_LINE"
    sleep "$INTERVAL" || true
done
) > "$MON_LOG" &
MON_PID=$!

# dmesg -w 可能在没有新消息时阻塞；放到独立进程组，便于完整清理管道
DMESG_MONITOR_TIMEOUT=$((DURATION + 300))
if command -v setsid >/dev/null 2>&1; then
  CRITICAL_ERR_PATTERN="$CRITICAL_ERR_PATTERN" ERR_LOG="$ERR_LOG" DMESG_MONITOR_TIMEOUT="$DMESG_MONITOR_TIMEOUT" \
    setsid bash -c 'timeout "$DMESG_MONITOR_TIMEOUT" dmesg -w 2>/dev/null | grep -Ei "$CRITICAL_ERR_PATTERN" > "$ERR_LOG"' &
else
  CRITICAL_ERR_PATTERN="$CRITICAL_ERR_PATTERN" ERR_LOG="$ERR_LOG" DMESG_MONITOR_TIMEOUT="$DMESG_MONITOR_TIMEOUT" \
    bash -c 'timeout "$DMESG_MONITOR_TIMEOUT" dmesg -w 2>/dev/null | grep -Ei "$CRITICAL_ERR_PATTERN" > "$ERR_LOG"' &
fi
ERR_PID=$!
ERR_PGID=$(ps -o pgid= "$ERR_PID" 2>/dev/null | tr -d ' ')

echo "[STAGE] monitor_started pids=mon:$MON_PID err:$ERR_PID err_pgid:${ERR_PGID:-N/A}"

sleep 2

# ===== 执行 stress-ng 压测 =====
echo "[STAGE] stress_start"

STRESS_GRACE_SECONDS=${STRESS_GRACE_SECONDS:-30}
STRESS_FORCE_KILL_AFTER=$((DURATION + STRESS_GRACE_SECONDS))

# 先创建日志文件，保证 tail 能正常工作
touch "$STRESS_LOG"

# 使用 setsid 将 stress-ng 放入独立进程组，便于后续精确 kill 整个进程组
# 输出直接写入文件，不经过管道，杜绝管道阻塞
if command -v setsid >/dev/null 2>&1; then
  setsid stress-ng \
    --cpu "${CPU_WORKERS}" \
    --cpu-method all \
    --vm "${VM_WORKERS}" \
    --vm-bytes "${VM_BYTES}" \
    --vm-method all \
    --vm-keep \
    --verify \
    --timeout "${DURATION}s" \
    --metrics-brief \
    > "$STRESS_LOG" 2>&1 &
else
  stress-ng \
    --cpu "${CPU_WORKERS}" \
    --cpu-method all \
    --vm "${VM_WORKERS}" \
    --vm-bytes "${VM_BYTES}" \
    --vm-method all \
    --vm-keep \
    --verify \
    --timeout "${DURATION}s" \
    --metrics-brief \
    > "$STRESS_LOG" 2>&1 &
fi
STRESS_PID=$!
STRESS_PGID=$(ps -o pgid= "$STRESS_PID" 2>/dev/null | tr -d ' ')

# 后台 tail 实时输出日志到 stdout，让平台能看见 stress-ng 进度
tail -n +1 -F "$STRESS_LOG" 2>/dev/null &
TAIL_PID=$!

# 主动等待循环：每 10s 检查一次，到点后主动 kill 进程组
# 不依赖 stress-ng 内部 --timeout 能否正常退出
# DURATION + 30s 宽限后强制结束
WAITED=0
while kill -0 "$STRESS_PID" 2>/dev/null; do
  sleep 10
  WAITED=$((WAITED + 10))

  # 预期 DURATION 已过 + STRESS_GRACE_SECONDS 宽限，强制结束
  if [ "$WAITED" -ge "$STRESS_FORCE_KILL_AFTER" ]; then
    echo "[WARN] stress-ng still running after ${WAITED}s, force killing PGID ${STRESS_PGID}"
    # 先 SIGTERM，等 10s（安全校验：PGID != $$ 才按组 kill，避免误杀脚本自身）
    if [ -n "${STRESS_PGID:-}" ] && [ "${STRESS_PGID:-}" != "0" ] && [ "${STRESS_PGID:-}" != "$$" ]; then
      kill -TERM "-${STRESS_PGID}" 2>/dev/null || true
    else
      _kill_tree "$STRESS_PID" TERM
    fi
    sleep 10
    # 仍然活着 → SIGKILL
    if kill -0 "$STRESS_PID" 2>/dev/null; then
      echo "[WARN] stress-ng still alive after SIGTERM, sending SIGKILL"
      if [ -n "${STRESS_PGID:-}" ] && [ "${STRESS_PGID:-}" != "0" ] && [ "${STRESS_PGID:-}" != "$$" ]; then
        kill -KILL "-${STRESS_PGID}" 2>/dev/null || true
      else
        _kill_tree "$STRESS_PID" KILL
      fi
    fi
    break
  fi
done

# 收集退出码
wait "$STRESS_PID" 2>/dev/null
STRESS_EXIT=$?

# 停止 tail
kill "$TAIL_PID" 2>/dev/null || true
wait "$TAIL_PID" 2>/dev/null || true

echo "[STAGE] stress_done exit_code=${STRESS_EXIT}"

# stress-ng 到点或异常退出后，先通知后台监控退出，避免主脚本收尾卡住
touch "$STOP_FILE" 2>/dev/null || true

# ===== 清理后台进程（带超时 wait，避免子进程 hang 阻塞主脚本） =====
echo "[STAGE] monitor_stop_start"

# 1. 通知监控循环退出
touch "$STOP_FILE" 2>/dev/null || true

# 2. 关闭资源监控进程（wait 最多 5s，超时则跳过）
if [ -n "${MON_PID:-}" ] && kill -0 "$MON_PID" 2>/dev/null; then
    kill "$MON_PID" 2>/dev/null || true
    _wait_pid_with_timeout "$MON_PID" 5
fi

# 3. 关闭 dmesg 监控进程组（wait 最多 5s）
if [ -n "${ERR_PGID:-}" ]; then
    _kill_process_group "$ERR_PGID" TERM
elif [ -n "${ERR_PID:-}" ]; then
    _kill_tree "$ERR_PID" TERM
fi
[ -n "${ERR_PID:-}" ] && _wait_pid_with_timeout "$ERR_PID" 5

# 4. 只清理当前脚本子进程，避免误杀系统里其他任务的 dmesg -w
pkill -P $$ dmesg 2>/dev/null || true
pkill -P $$ grep 2>/dev/null || true

sleep 1
echo "[STAGE] monitor_stop_done"

# ===== 计算统计指标 =====
echo "[STAGE] report_txt_start"

LOAD1_AVG=$(awk -F',' 'NR>1 {sum+=$2; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
LOAD1_MAX=$(awk -F',' 'NR>1 {if($2>max)max=$2} END{printf "%.2f",max+0}' "$MON_LOG")
LOAD5_AVG=$(awk -F',' 'NR>1 {sum+=$3; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
LOAD15_AVG=$(awk -F',' 'NR>1 {sum+=$4; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")

MEM_USED_AVG=$(awk -F',' 'NR>1 {sum+=$6; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
MEM_USED_MAX=$(awk -F',' 'NR>1 {if($6>max)max=$6} END{printf "%.0f",max+0}' "$MON_LOG")
MEM_AVAIL_MIN=$(awk -F',' 'NR>1 {if(NR==2 || $8<min)min=$8} END{printf "%.0f",min+0}' "$MON_LOG")
SWAP_USED_MAX=$(awk -F',' 'NR>1 {if($10>max)max=$10} END{printf "%.0f",max+0}' "$MON_LOG")

# Swap 判定策略：短暂超过阈值不判失败；只有“持续超阈值 + 可用内存很低”才 FAIL
SWAP_SUSTAIN_SECONDS=${SWAP_SUSTAIN_SECONDS:-300}
MEM_AVAIL_FAIL_PERCENT=${MEM_AVAIL_FAIL_PERCENT:-5}
MEM_TOTAL_MB=$(awk -F',' 'NR==2 {printf "%.0f", $5+0; exit}' "$MON_LOG")
[ -z "$MEM_TOTAL_MB" ] || [ "$MEM_TOTAL_MB" = "0" ] && MEM_TOTAL_MB=$(free -m | awk '/Mem:/ {print $2}')
MEM_AVAIL_FAIL_MB=$(( MEM_TOTAL_MB * MEM_AVAIL_FAIL_PERCENT / 100 ))
[ "$MEM_AVAIL_FAIL_MB" -lt 1024 ] && MEM_AVAIL_FAIL_MB=1024

SWAP_OVER_THRESHOLD_SAMPLES=$(awk -F',' -v th="$SWAP_FAIL_MB" 'NR>1 && $10>th {n++} END{print n+0}' "$MON_LOG")
SWAP_OVER_MAX_CONSECUTIVE_SAMPLES=$(awk -F',' -v th="$SWAP_FAIL_MB" 'NR>1 {if($10>th){cur++; if(cur>max)max=cur}else{cur=0}} END{print max+0}' "$MON_LOG")
SWAP_LOW_MEM_MAX_CONSECUTIVE_SAMPLES=$(awk -F',' -v th="$SWAP_FAIL_MB" -v low="$MEM_AVAIL_FAIL_MB" 'NR>1 {if($10>th && $8<=low){cur++; if(cur>max)max=cur}else{cur=0}} END{print max+0}' "$MON_LOG")
SWAP_OVER_MAX_SECONDS=$(( SWAP_OVER_MAX_CONSECUTIVE_SAMPLES * INTERVAL ))
SWAP_LOW_MEM_MAX_SECONDS=$(( SWAP_LOW_MEM_MAX_CONSECUTIVE_SAMPLES * INTERVAL ))

ERROR_COUNT=$(grep -Ei "$CRITICAL_ERR_PATTERN" "$ERR_LOG" 2>/dev/null | wc -l)
STRESS_ERROR=$(grep -Ei "verification failed|aborted|segmentation fault|bus error|out of memory|oom-killer|killed process|stress-ng: fail:" "$STRESS_LOG" 2>/dev/null || true)

RESULT="PASS"
REASON="No critical error detected."

if [ "$STRESS_EXIT" != "0" ]; then
    RESULT="FAIL"
    REASON="stress-ng exited abnormally. Exit code: ${STRESS_EXIT}"
fi

if [ "$SWAP_LOW_MEM_MAX_SECONDS" -ge "$SWAP_SUSTAIN_SECONDS" ]; then
    RESULT="FAIL"
    REASON="Swap usage stayed high with low available memory for ${SWAP_LOW_MEM_MAX_SECONDS}s >= ${SWAP_SUSTAIN_SECONDS}s. Swap max: ${SWAP_USED_MAX} MB, threshold: ${SWAP_FAIL_MB} MB, available memory low threshold: ${MEM_AVAIL_FAIL_MB} MB."
elif [ "$RESULT" = "PASS" ] && [ "$SWAP_USED_MAX" -gt "$SWAP_FAIL_MB" ]; then
    REASON="No critical error detected. Swap exceeded threshold briefly or without low available memory; treated as PASS."
fi

if [ "$ERROR_COUNT" != "0" ]; then
    RESULT="FAIL"
    REASON="Critical kernel error detected."
fi

if [ -n "$STRESS_ERROR" ]; then
    RESULT="FAIL"
    REASON="stress-ng reported real critical error."
fi

cat > "$REPORT" << EOR
CPU + 内存稳定性压力测试报告

一、测试概述
本次测试针对服务器 CPU 与内存进行持续高负载压力测试，主要验证设备在长时间满载条件下的计算稳定性、内存稳定性、系统可靠性及异常告警情况。

二、测试对象
操作系统              : ${OS_INFO}
CPU型号               : ${CPU_MODEL}
逻辑线程数            : ${CPU_CORES}
内存总量              : ${MEM_TOTAL}

三、测试方法
测试工具              : stress-ng
CPU压力线程           : ${CPU_WORKERS}
CPU测试方法           : all
内存压力线程          : ${VM_WORKERS}
内存占用比例          : ${VM_BYTES}
内存测试方法          : all
数据校验              : verify enabled
测试时长              : ${DURATION} 秒
脚本强制结束阈值      : ${STRESS_FORCE_KILL_AFTER} 秒
采样间隔              : ${INTERVAL} 秒
Swap瞬时阈值          : ${SWAP_FAIL_MB} MB
Swap持续失败时间阈值  : ${SWAP_SUSTAIN_SECONDS} 秒
可用内存低阈值        : ${MEM_AVAIL_FAIL_MB} MB (${MEM_AVAIL_FAIL_PERCENT}%)

四、测试结果汇总

1. CPU负载
平均1分钟负载          : ${LOAD1_AVG}
最高1分钟负载          : ${LOAD1_MAX}
平均5分钟负载          : ${LOAD5_AVG}
平均15分钟负载         : ${LOAD15_AVG}

2. 内存表现
平均已用内存          : ${MEM_USED_AVG} MB
最高已用内存          : ${MEM_USED_MAX} MB
最低可用内存          : ${MEM_AVAIL_MIN} MB
最大Swap使用          : ${SWAP_USED_MAX} MB
Swap超阈采样数        : ${SWAP_OVER_THRESHOLD_SAMPLES}
Swap连续超阈最长时长  : ${SWAP_OVER_MAX_SECONDS} 秒
Swap+低可用内存连续最长时长 : ${SWAP_LOW_MEM_MAX_SECONDS} 秒

3. 异常检查
stress-ng退出码        : ${STRESS_EXIT}
重大内核异常数量      : ${ERROR_COUNT}
stress-ng严重错误      : $( [ -z "$STRESS_ERROR" ] && echo "未发现" || echo "发现严重错误，请查看 ${STRESS_LOG}" )
OOM / MCE / ECC / Thermal Throttling : $( [ "$ERROR_COUNT" = "0" ] && echo "未发现重大异常" || echo "发现重大异常，请查看 ${ERR_LOG}" )

说明：
EDAC模块加载、MCE功能启用、thermal governor注册等系统初始化信息不作为失败依据。
stress-ng普通提示中的 failed 字样不作为失败依据。
仅当出现 OOM、Killed process、ECC uncorrected error、Machine Check Error、Hardware Error、Thermal Throttling、verification failed、segmentation fault 等重大异常时，才判定为不通过。
Swap 短暂超过 ${SWAP_FAIL_MB} MB 不判失败；只有 Swap 持续超阈且可用内存持续低于 ${MEM_AVAIL_FAIL_MB} MB 达到 ${SWAP_SUSTAIN_SECONDS} 秒，才判定为失败。

五、综合判定
测试结果              : ${RESULT}
判定原因              : ${REASON}

六、结论
$(if [ "$RESULT" = "PASS" ]; then
cat << PASS_TEXT
本次 CPU + 内存压力测试期间，系统在高负载条件下持续运行，未发现 OOM、MCE、ECC、thermal throttling 等重大异常，stress-ng 未报告计算或内存校验错误。

综合判断：该服务器在本次测试条件下 CPU 与内存运行稳定，满足生产环境持续运行要求。
PASS_TEXT
else
cat << FAIL_TEXT
本次 CPU + 内存压力测试未通过。测试期间检测到重大异常或资源风险。建议结合 stress-ng 日志、资源监控日志和内核错误日志进一步排查 CPU、内存、散热、供电或系统配置问题。
FAIL_TEXT
fi)

七、原始文件
stress-ng日志          : ${STRESS_LOG}
资源监控日志          : ${MON_LOG}
内核错误日志          : ${ERR_LOG}
Excel报告             : ${XLSX_REPORT}

八、报告生成信息
报告生成时间          : $(date "+%F %T")
EOR

echo "[STAGE] report_txt_done"

# ===== 生成 XLSX 报告 =====
echo "[STAGE] report_xlsx_start"

set +e  # xlsx 生成可能超时或失败，不影响脚本退出
# xlsx 生成最多允许 600 秒（10 分钟），超时则跳过但保留其他文件
XLSX_OK=0
XLSX_DURATION=0
XLSX_TIMEOUT=600
XLSX_PY="/tmp/gen_xlsx_${TIME_TAG}.py"

if command -v timeout >/dev/null 2>&1; then
XLSX_START_TS=$(date +%s)

# 写入临时 Python 脚本（cat 位置顶格，避免 heredoc 缩进问题）
cat > "$XLSX_PY" << PYEOF
import csv
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter

report = Path("${REPORT}")
stress_log = Path("${STRESS_LOG}")
mon_log = Path("${MON_LOG}")
err_log = Path("${ERR_LOG}")
xlsx = Path("${XLSX_REPORT}")

result = "${RESULT}"
reason = "${REASON}"

wb = Workbook()
ws = wb.active
ws.title = "Summary"
raw = wb.create_sheet("RawReport")
stress = wb.create_sheet("StressLog")
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
ws["A1"] = "CPU + 内存稳定性压力测试报告"
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
    ws.cell(row=row, column=1, value=key)
    ws.cell(row=row, column=2, value=value)
    for col in range(1, 3):
        cell = ws.cell(row=row, column=col)
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=gray)
    ws.cell(row=row, column=1).font = Font(bold=True)
    return row + 1

r = 3
r = section(r, "一、测试对象")
for k, v in [
    ("操作系统", "${OS_INFO}"),
    ("CPU型号", "${CPU_MODEL}"),
    ("逻辑线程数", "${CPU_CORES}"),
    ("内存总量", "${MEM_TOTAL}"),
]:
    r = kv(r, k, v)

r += 1
r = section(r, "二、测试方法")
for k, v in [
    ("测试工具", "stress-ng"),
    ("CPU压力线程", "${CPU_WORKERS}"),
    ("CPU测试方法", "all"),
    ("内存压力线程", "${VM_WORKERS}"),
    ("内存占用比例", "${VM_BYTES}"),
    ("内存测试方法", "all"),
    ("数据校验", "verify enabled"),
    ("测试时长", "${DURATION} 秒"),
    ("脚本强制结束阈值", "${STRESS_FORCE_KILL_AFTER} 秒"),
    ("采样间隔", "${INTERVAL} 秒"),
    ("Swap瞬时阈值", "${SWAP_FAIL_MB} MB"),
    ("Swap持续失败时间阈值", "${SWAP_SUSTAIN_SECONDS} 秒"),
    ("可用内存低阈值", "${MEM_AVAIL_FAIL_MB} MB (${MEM_AVAIL_FAIL_PERCENT}%)"),
]:
    r = kv(r, k, v)

r += 1
r = section(r, "三、测试结果汇总")

headers = ["类别", "指标", "数值"]
for i, h in enumerate(headers, 1):
    cell = ws.cell(row=r, column=i, value=h)
    cell.font = Font(bold=True, color=white)
    cell.fill = PatternFill("solid", fgColor=dark)
    cell.border = border
r += 1

rows_data = [
    ("CPU负载", "平均1分钟负载", "${LOAD1_AVG}"),
    ("CPU负载", "最高1分钟负载", "${LOAD1_MAX}"),
    ("CPU负载", "平均5分钟负载", "${LOAD5_AVG}"),
    ("CPU负载", "平均15分钟负载", "${LOAD15_AVG}"),
    ("内存表现", "平均已用内存", "${MEM_USED_AVG} MB"),
    ("内存表现", "最高已用内存", "${MEM_USED_MAX} MB"),
    ("内存表现", "最低可用内存", "${MEM_AVAIL_MIN} MB"),
    ("内存表现", "最大Swap使用", "${SWAP_USED_MAX} MB"),
    ("异常检查", "stress-ng退出码", "${STRESS_EXIT}"),
    ("异常检查", "重大内核异常数量", "${ERROR_COUNT}"),
]

for row_data in rows_data:
    for c, v in enumerate(row_data, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    r += 1

r += 1
r = section(r, "四、综合判定")
r = kv(r, "测试结果", result)
ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=green if result == "PASS" else red)
ws.cell(row=r - 1, column=2).font = Font(bold=True)
r = kv(r, "判定原因", reason)
r = kv(r, "报告生成时间", "$(date "+%F %T")")

for col, width in {"A": 18, "B": 34, "C": 24, "D": 14, "E": 14, "F": 14, "G": 14, "H": 14}.items():
    ws.column_dimensions[col].width = width

if report.exists():
    for line in report.read_text(errors="ignore").splitlines():
        raw.append([line])
raw.column_dimensions["A"].width = 130

if stress_log.exists():
    for line in stress_log.read_text(errors="ignore").splitlines():
        stress.append([line])
stress.column_dimensions["A"].width = 130

if err_log.exists() and err_log.stat().st_size > 0:
    for line in err_log.read_text(errors="ignore").splitlines():
        err.append([line])
else:
    err.append(["No critical kernel error detected."])
err.column_dimensions["A"].width = 130

def to_number(v):
    try:
        return float(str(v).strip())
    except Exception:
        return v

if mon_log.exists():
    with mon_log.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for idx, row_data in enumerate(reader, 1):
            out = []
            for j, val in enumerate(row_data, 1):
                if idx > 1 and j >= 2:
                    out.append(to_number(val))
                else:
                    out.append(val.strip() if isinstance(val, str) else val)
            mon.append(out)

for sheet in [raw, stress, mon, err]:
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=dark)

for col in range(1, mon.max_column + 1):
    mon.column_dimensions[get_column_letter(col)].width = 22

# 生成图表：按完整测试时长动态抽样，不再只截取前 500 行
chart_data = wb.create_sheet("ChartData")
if mon.max_row > 2 and mon.max_column >= 10:
    CHART_MAX_POINTS = 600
    total_data_rows = mon.max_row - 1
    step = max(1, total_data_rows // CHART_MAX_POINTS)

    headers = [mon.cell(row=1, column=c).value for c in range(1, mon.max_column + 1)]
    chart_data.append(headers)

    selected_rows = list(range(2, mon.max_row + 1, step))
    if selected_rows[-1] != mon.max_row:
        selected_rows.append(mon.max_row)

    for src_row in selected_rows:
        chart_data.append([mon.cell(row=src_row, column=c).value for c in range(1, mon.max_column + 1)])

    chart_data.freeze_panes = "A2"
    for col in range(1, chart_data.max_column + 1):
        chart_data.column_dimensions[get_column_letter(col)].width = 22
    for cell in chart_data[1]:
        cell.font = Font(bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=dark)

    def add_chart(title, col, pos):
        chart = LineChart()
        chart.title = title
        chart.y_axis.title = title
        chart.x_axis.title = "Time"
        data = Reference(chart_data, min_col=col, min_row=1, max_row=chart_data.max_row)
        cats = Reference(chart_data, min_col=1, min_row=2, max_row=chart_data.max_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 7
        chart.width = 14
        ws.add_chart(chart, pos)

    add_chart("Load 1min", 2, "J3")
    add_chart("Load 5min", 3, "J18")
    add_chart("Load 15min", 4, "J33")
    add_chart("Memory Used(MB)", 6, "J48")
    add_chart("Memory Available(MB)", 8, "J63")
    add_chart("Swap Used(MB)", 10, "J78")
else:
    chart_data.append(["No monitor data available for charts."])

# 仅对 Summary 和 Monitor 表应用边框（避免全表爆内存）
for target_sheet in [ws, mon]:
    for row in target_sheet.iter_rows():
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(wrap_text=True, vertical="center")

wb.save(xlsx)
print(f"XLSX Report : {xlsx}")
print("XLSX_GENERATE_OK")
PYEOF

timeout "$XLSX_TIMEOUT" python3 "$XLSX_PY" 2>&1
XLSX_EXIT_CODE=$?
rm -f "$XLSX_PY"
XLSX_END_TS=$(date +%s)
XLSX_DURATION=$(( XLSX_END_TS - XLSX_START_TS ))
if [ "$XLSX_EXIT_CODE" = "124" ]; then
    echo "[STAGE] report_xlsx_timeout duration=${XLSX_DURATION}s limit=${XLSX_TIMEOUT}s"
elif [ "$XLSX_EXIT_CODE" = "0" ]; then
    XLSX_OK=1
    echo "[STAGE] report_xlsx_done duration=${XLSX_DURATION}s"
else
    echo "[STAGE] report_xlsx_failed exit_code=${XLSX_EXIT_CODE} duration=${XLSX_DURATION}s"
fi
else
    echo "[WARN] timeout command not available, running xlsx generation without timeout"
cat > "$XLSX_PY" << PYEOF
import csv
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter

report = Path("${REPORT}")
stress_log = Path("${STRESS_LOG}")
mon_log = Path("${MON_LOG}")
err_log = Path("${ERR_LOG}")
xlsx = Path("${XLSX_REPORT}")

result = "${RESULT}"
reason = "${REASON}"

wb = Workbook()
ws = wb.active
ws.title = "Summary"
raw = wb.create_sheet("RawReport")
stress = wb.create_sheet("StressLog")
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
ws["A1"] = "CPU + 内存稳定性压力测试报告"
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
    ws.cell(row=row, column=1, value=key)
    ws.cell(row=row, column=2, value=value)
    for col in range(1, 3):
        cell = ws.cell(row=row, column=col)
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=gray)
    ws.cell(row=row, column=1).font = Font(bold=True)
    return row + 1

r = 3
r = section(r, "一、测试对象")
for k, v in [
    ("操作系统", "${OS_INFO}"),
    ("CPU型号", "${CPU_MODEL}"),
    ("逻辑线程数", "${CPU_CORES}"),
    ("内存总量", "${MEM_TOTAL}"),
]:
    r = kv(r, k, v)

r += 1
r = section(r, "二、测试方法")
for k, v in [
    ("测试工具", "stress-ng"),
    ("CPU压力线程", "${CPU_WORKERS}"),
    ("CPU测试方法", "all"),
    ("内存压力线程", "${VM_WORKERS}"),
    ("内存占用比例", "${VM_BYTES}"),
    ("内存测试方法", "all"),
    ("数据校验", "verify enabled"),
    ("测试时长", "${DURATION} 秒"),
    ("脚本强制结束阈值", "${STRESS_FORCE_KILL_AFTER} 秒"),
    ("采样间隔", "${INTERVAL} 秒"),
    ("Swap瞬时阈值", "${SWAP_FAIL_MB} MB"),
    ("Swap持续失败时间阈值", "${SWAP_SUSTAIN_SECONDS} 秒"),
    ("可用内存低阈值", "${MEM_AVAIL_FAIL_MB} MB (${MEM_AVAIL_FAIL_PERCENT}%)"),
]:
    r = kv(r, k, v)

r += 1
r = section(r, "三、测试结果汇总")

headers = ["类别", "指标", "数值"]
for i, h in enumerate(headers, 1):
    cell = ws.cell(row=r, column=i, value=h)
    cell.font = Font(bold=True, color=white)
    cell.fill = PatternFill("solid", fgColor=dark)
    cell.border = border
r += 1

rows_data = [
    ("CPU负载", "平均1分钟负载", "${LOAD1_AVG}"),
    ("CPU负载", "最高1分钟负载", "${LOAD1_MAX}"),
    ("CPU负载", "平均5分钟负载", "${LOAD5_AVG}"),
    ("CPU负载", "平均15分钟负载", "${LOAD15_AVG}"),
    ("内存表现", "平均已用内存", "${MEM_USED_AVG} MB"),
    ("内存表现", "最高已用内存", "${MEM_USED_MAX} MB"),
    ("内存表现", "最低可用内存", "${MEM_AVAIL_MIN} MB"),
    ("内存表现", "最大Swap使用", "${SWAP_USED_MAX} MB"),
    ("异常检查", "stress-ng退出码", "${STRESS_EXIT}"),
    ("异常检查", "重大内核异常数量", "${ERROR_COUNT}"),
]

for row_data in rows_data:
    for c, v in enumerate(row_data, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    r += 1

r += 1
r = section(r, "四、综合判定")
r = kv(r, "测试结果", result)
ws.cell(row=r - 1, column=2).fill = PatternFill("solid", fgColor=green if result == "PASS" else red)
ws.cell(row=r - 1, column=2).font = Font(bold=True)
r = kv(r, "判定原因", reason)
r = kv(r, "报告生成时间", "$(date "+%F %T")")

for col, width in {"A": 18, "B": 34, "C": 24, "D": 14, "E": 14, "F": 14, "G": 14, "H": 14}.items():
    ws.column_dimensions[col].width = width

if report.exists():
    for line in report.read_text(errors="ignore").splitlines():
        raw.append([line])
raw.column_dimensions["A"].width = 130

if stress_log.exists():
    for line in stress_log.read_text(errors="ignore").splitlines():
        stress.append([line])
stress.column_dimensions["A"].width = 130

if err_log.exists() and err_log.stat().st_size > 0:
    for line in err_log.read_text(errors="ignore").splitlines():
        err.append([line])
else:
    err.append(["No critical kernel error detected."])
err.column_dimensions["A"].width = 130

def to_number(v):
    try:
        return float(str(v).strip())
    except Exception:
        return v

if mon_log.exists():
    with mon_log.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for idx, row_data in enumerate(reader, 1):
            out = []
            for j, val in enumerate(row_data, 1):
                if idx > 1 and j >= 2:
                    out.append(to_number(val))
                else:
                    out.append(val.strip() if isinstance(val, str) else val)
            mon.append(out)

for sheet in [raw, stress, mon, err]:
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=dark)

for col in range(1, mon.max_column + 1):
    mon.column_dimensions[get_column_letter(col)].width = 22

chart_data = wb.create_sheet("ChartData")
if mon.max_row > 2 and mon.max_column >= 10:
    CHART_MAX_POINTS = 600
    total_data_rows = mon.max_row - 1
    step = max(1, total_data_rows // CHART_MAX_POINTS)

    headers = [mon.cell(row=1, column=c).value for c in range(1, mon.max_column + 1)]
    chart_data.append(headers)

    selected_rows = list(range(2, mon.max_row + 1, step))
    if selected_rows[-1] != mon.max_row:
        selected_rows.append(mon.max_row)

    for src_row in selected_rows:
        chart_data.append([mon.cell(row=src_row, column=c).value for c in range(1, mon.max_column + 1)])

    chart_data.freeze_panes = "A2"
    for col in range(1, chart_data.max_column + 1):
        chart_data.column_dimensions[get_column_letter(col)].width = 22
    for cell in chart_data[1]:
        cell.font = Font(bold=True, color=white)
        cell.fill = PatternFill("solid", fgColor=dark)

    def add_chart(title, col, pos):
        chart = LineChart()
        chart.title = title
        chart.y_axis.title = title
        chart.x_axis.title = "Time"
        data = Reference(chart_data, min_col=col, min_row=1, max_row=chart_data.max_row)
        cats = Reference(chart_data, min_col=1, min_row=2, max_row=chart_data.max_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 7
        chart.width = 14
        ws.add_chart(chart, pos)

    add_chart("Load 1min", 2, "J3")
    add_chart("Load 5min", 3, "J18")
    add_chart("Load 15min", 4, "J33")
    add_chart("Memory Used(MB)", 6, "J48")
    add_chart("Memory Available(MB)", 8, "J63")
    add_chart("Swap Used(MB)", 10, "J78")
else:
    chart_data.append(["No monitor data available for charts."])

for target_sheet in [ws, mon]:
    for row in target_sheet.iter_rows():
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(wrap_text=True, vertical="center")

wb.save(xlsx)
print(f"XLSX Report : {xlsx}")
print("XLSX_GENERATE_OK")
PYEOF

python3 "$XLSX_PY" 2>&1
XLSX_EXIT_CODE=$?
rm -f "$XLSX_PY"
if [ "$XLSX_EXIT_CODE" = "0" ]; then
    XLSX_OK=1
fi
echo "[STAGE] report_xlsx_done (no-timeout mode) exit_code=${XLSX_EXIT_CODE}"
fi

# 最终输出
XLSX_FINAL_STATUS="NOT_GENERATED"
[ "$XLSX_OK" = "1" ] && XLSX_FINAL_STATUS="GENERATED"

echo
echo "======================================"
echo "CPU + Memory Stress Test Finished"
echo "Result       : ${RESULT}"
echo "Reason       : ${REASON}"
echo "XLSX Status  : ${XLSX_FINAL_STATUS} (duration: ${XLSX_DURATION}s)"
echo "CPU Workers  : ${CPU_WORKERS}"
echo "VM Workers   : ${VM_WORKERS}"
echo "Stress Log   : ${STRESS_LOG}"
echo "Monitor CSV  : ${MON_LOG}"
echo "Kernel Error : ${ERR_LOG}"
echo "Text Report  : ${REPORT}"
echo "XLSX Report  : ${XLSX_REPORT}"
echo "======================================"

FINAL_EXIT=0
[ "$RESULT" = "PASS" ] || FINAL_EXIT=1

echo "[STAGE] script_exit exit_code=${FINAL_EXIT}"
exit "$FINAL_EXIT"

