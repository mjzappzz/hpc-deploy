#!/bin/bash

set -e

echo "[INFO] Checking and installing dependencies..."

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

echo "[INFO] Dependency check done."

DURATION=${1:-43200}
INTERVAL=${2:-2}
TEST_DIR=${3:-$(pwd)}

CPU_CORES=$(nproc)
HDD_WORKERS=$(( CPU_CORES / 16 ))
[ "$HDD_WORKERS" -lt 4 ] && HDD_WORKERS=4
[ "$HDD_WORKERS" -gt 32 ] && HDD_WORKERS=32

TIME_TAG=$(date +%F_%H%M%S)
WORKDIR=$(pwd)

STRESS_LOG="${WORKDIR}/stress_disk_${TIME_TAG}.log"
MON_LOG="${WORKDIR}/disk_monitor_${TIME_TAG}.csv"
ERR_LOG="${WORKDIR}/disk_error_${TIME_TAG}.log"
REPORT="${WORKDIR}/disk_stress_report_${TIME_TAG}.txt"
XLSX_REPORT="${WORKDIR}/disk_stress_report_${TIME_TAG}.xlsx"

CRITICAL_ERR_PATTERN="i/o error|blk_update_request|buffer i/o error|nvme.*error|reset controller|aborting command|medium error|read error|write error|filesystem error|xfs.*error|ext4.*error|bad sector|uncorrected error"

mkdir -p "$TEST_DIR"

MOUNT_SRC=$(df -P "$TEST_DIR" | awk 'NR==2 {print $1}')
MOUNT_POINT=$(df -P "$TEST_DIR" | awk 'NR==2 {print $6}')
FS_TYPE=$(df -T "$TEST_DIR" | awk 'NR==2 {print $2}')

DISK_DEV=$(lsblk -no PKNAME "$MOUNT_SRC" 2>/dev/null | head -1)
[ -z "$DISK_DEV" ] && DISK_DEV=$(basename "$MOUNT_SRC")

DISK_MODEL=$(cat /sys/block/${DISK_DEV}/device/model 2>/dev/null | xargs || true)
if [ -z "$DISK_MODEL" ] || [ "$DISK_MODEL" = "Unknown" ]; then
    DISK_MODEL_LINE=""
else
    DISK_MODEL_LINE="磁盘型号              : ${DISK_MODEL}"
fi

DISK_SIZE=$(lsblk -dn -o SIZE "/dev/${DISK_DEV}" 2>/dev/null | xargs || echo "Unknown")
OS_INFO=$(cat /etc/os-release 2>/dev/null | awk -F= '/^PRETTY_NAME=/ {gsub(/"/,"",$2); print $2}')

echo "======================================"
echo "Disk Write Stability Test Start"
echo "Test Dir    : ${TEST_DIR}"
echo "Mount Point : ${MOUNT_POINT}"
echo "Device      : /dev/${DISK_DEV}"
echo "Filesystem  : ${FS_TYPE}"
echo "Workers     : ${HDD_WORKERS}"
echo "Duration    : ${DURATION}"
echo "Interval    : ${INTERVAL}s"
echo "Mode        : write only, wr-rnd"
echo "======================================"

(
echo "timestamp,used_GB,avail_GB,use_percent,write_MBps,write_iops,await_ms,util_percent"

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

            w_ios=b[8]-a[8];
            w_sec=b[10]-a[10];
            w_ticks=b[11]-a[11];
            io_ticks=b[13]-a[13];

            write_MBps=(w_sec*512/1024/1024)/dt;
            write_iops=w_ios/dt;

            await=0;
            if (w_ios>0) await=w_ticks/w_ios;

            util=io_ticks/(dt*10);
            if (util>100) util=100;

            printf "%.2f,%.2f,%.2f,%.2f", write_MBps,write_iops,await,util
        }')
    else
        METRICS="0,0,0,0"
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

(
  cd "$TEST_DIR" || exit 1

  echo "===== stress-ng disk test start ====="
  echo "Start Time : $(date '+%F %T')"
  echo "Test Dir   : ${TEST_DIR}"
  echo "Workers    : ${HDD_WORKERS}"
  echo "Duration   : ${DURATION}"
  echo "Mode       : wr-rnd"
  echo

  stdbuf -oL -eL stress-ng \
    --hdd ${HDD_WORKERS} \
    --hdd-bytes 20G \
    --hdd-opts wr-rnd \
    --verify \
    --timeout "${DURATION}" \
    --metrics-brief \
    --verbose

  RET=$?

  echo
  echo "End Time   : $(date '+%F %T')"
  echo "Exit Code  : ${RET}"
  echo "===== stress-ng disk test end ====="

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

USED_MAX=$(awk -F',' 'NR>1 {if($2>max)max=$2} END{print max+0}' "$MON_LOG")
AVAIL_MIN=$(awk -F',' 'NR>1 {if(NR==2 || $3<min)min=$3} END{print min+0}' "$MON_LOG")
USE_MAX=$(awk -F',' 'NR>1 {if($4>max)max=$4} END{print max+0}' "$MON_LOG")

WRITE_AVG=$(awk -F',' 'NR>1 {sum+=$5; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
WRITE_MAX=$(awk -F',' 'NR>1 {if($5>max)max=$5} END{printf "%.2f",max+0}' "$MON_LOG")

WIOPS_AVG=$(awk -F',' 'NR>1 {sum+=$6; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
WIOPS_MAX=$(awk -F',' 'NR>1 {if($6>max)max=$6} END{printf "%.2f",max+0}' "$MON_LOG")

AWAIT_AVG=$(awk -F',' 'NR>1 {sum+=$7; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
AWAIT_MAX=$(awk -F',' 'NR>1 {if($7>max)max=$7} END{printf "%.2f",max+0}' "$MON_LOG")

UTIL_AVG=$(awk -F',' 'NR>1 {sum+=$8; n++} END{if(n>0) printf "%.2f",sum/n; else print "0"}' "$MON_LOG")
UTIL_MAX=$(awk -F',' 'NR>1 {if($8>max)max=$8} END{printf "%.2f",max+0}' "$MON_LOG")

ERROR_COUNT=$(grep -Ei "$CRITICAL_ERR_PATTERN" "$ERR_LOG" | wc -l)
STRESS_ERROR=$(grep -Ei "verification failed|aborted|segmentation fault|bus error|out of memory|oom-killer|killed process|input/output error|read error|write error|stress-ng: fail:" "$STRESS_LOG" || true)

RESULT="PASS"
REASON="No critical error detected."

if [ "$STRESS_EXIT" != "0" ]; then
    RESULT="FAIL"
    REASON="stress-ng exited abnormally. Exit code: ${STRESS_EXIT}"
fi

if [ "$ERROR_COUNT" != "0" ]; then
    RESULT="FAIL"
    REASON="Critical kernel disk error detected."
fi

if [ -n "$STRESS_ERROR" ]; then
    RESULT="FAIL"
    REASON="stress-ng reported real critical disk error."
fi

cat > "$REPORT" << EOR
磁盘写入稳定性压力测试报告

一、测试对象
操作系统              : ${OS_INFO}
测试目录              : ${TEST_DIR}
挂载点                : ${MOUNT_POINT}
挂载源                : ${MOUNT_SRC}
磁盘设备              : /dev/${DISK_DEV}
${DISK_MODEL_LINE}
磁盘容量              : ${DISK_SIZE}
文件系统              : ${FS_TYPE}

二、测试方法
测试工具              : stress-ng
HDD压力线程           : ${HDD_WORKERS}
线程计算方式          : nproc / 16，限制范围 4~32
HDD测试模式           : wr-rnd
单Worker数据量        : 20G
测试类型              : 随机写稳定性测试
数据校验              : verify enabled
测试时长              : ${DURATION}
采样间隔              : ${INTERVAL} 秒
测试目录              : ${TEST_DIR}

三、测试结果统计
最高已用空间          : ${USED_MAX} GB
最低可用空间          : ${AVAIL_MIN} GB
最高使用率            : ${USE_MAX} %

平均写入速度          : ${WRITE_AVG} MB/s
峰值写入速度          : ${WRITE_MAX} MB/s

平均写IOPS            : ${WIOPS_AVG}
峰值写IOPS            : ${WIOPS_MAX}

平均写await           : ${AWAIT_AVG} ms
最大写await           : ${AWAIT_MAX} ms

平均util              : ${UTIL_AVG} %
最大util              : ${UTIL_MAX} %


四、异常检查
stress-ng退出码        : ${STRESS_EXIT}
重大内核磁盘异常数量  : ${ERROR_COUNT}
stress-ng严重错误      : $( [ -z "$STRESS_ERROR" ] && echo "未发现" || echo "发现严重错误，请查看 ${STRESS_LOG}" )

五、综合判定
测试结果              : ${RESULT}
判定原因              : ${REASON}

六、结论
$(if [ "$RESULT" = "PASS" ]; then
cat << PASS_TEXT
本次硬盘写入稳定性压力测试期间，指定目录所在磁盘持续进行随机写入压力测试，未发现 stress-ng 校验错误、I/O 错误、NVMe 控制器异常或文件系统重大错误。

综合判断：本次测试通过，磁盘在持续随机写入负载下运行稳定，未发现数据校验失败、文件系统异常或内核级磁盘故障。

PASS_TEXT
else
cat << FAIL_TEXT
本次硬盘写入稳定性压力测试未通过。建议结合 stress-ng 日志、磁盘监控日志、dmesg 日志、SMART/NVMe 健康状态进一步排查。
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
ws["A1"] = "磁盘写入稳定性压力测试报告"
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
])
for k, v in test_object_rows:
    r = kv(r, k, v)

r += 1
r = section(r, "二、测试方法")
for k, v in [
    ("测试工具", "stress-ng"),
    ("HDD压力线程", "${HDD_WORKERS}"),
    ("线程计算方式", "nproc / 16，限制范围 4~32"),
    ("HDD测试模式", "wr-rnd"),
    ("单Worker数据量", "20G"),
    ("测试类型", "随机写稳定性测试"),
    ("数据校验", "verify enabled"),
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

    ("运行状态", "平均写入速度", "${WRITE_AVG} MB/s"),
    ("运行状态", "峰值写入速度", "${WRITE_MAX} MB/s"),
    ("运行状态", "平均写IOPS", "${WIOPS_AVG}"),
    ("运行状态", "峰值写IOPS", "${WIOPS_MAX}"),
    ("运行状态", "平均写await", "${AWAIT_AVG} ms"),
    ("运行状态", "最大写await", "${AWAIT_MAX} ms"),
    ("运行状态", "平均util", "${UTIL_AVG} %"),
    ("运行状态", "最大util", "${UTIL_MAX} %"),

    ("异常检查", "stress-ng退出码", "${STRESS_EXIT}"),
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
                    out.append(to_number(val))
                else:
                    out.append(clean_excel_text(val.strip()) if isinstance(val, str) else val)
            mon.append(out)

for sheet in [raw, stress, mon, err]:
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=dark)

for col in range(1, mon.max_column + 1):
    mon.column_dimensions[get_column_letter(col)].width = 22

if mon.max_row > 2 and mon.max_column >= 8:
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

    add_chart("写入速度变化趋势(MB/s)", 5, "J3")
    add_chart("写IOPS变化趋势", 6, "J18")
    add_chart("写await变化趋势(ms)", 7, "J33")
    add_chart("磁盘util变化趋势(%)", 8, "J48")


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
echo "Disk Write Stability Test Finished"
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

