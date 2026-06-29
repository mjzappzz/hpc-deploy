#!/bin/bash

set -e

# ===== 自动检测系统并安装依赖 =====
echo "[INFO] Checking and installing dependencies..."

install_deps() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "[ERROR] 请使用 root 用户运行，或使用 sudo"
        exit 1
    fi

    NEED_INSTALL=0

    if ! command -v nvidia-smi >/dev/null 2>&1; then
        echo "[ERROR] nvidia-smi not found，请先安装 NVIDIA 驱动"
        exit 1
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

    if ! command -v make >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! command -v git >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! command -v gcc >/dev/null 2>&1 && ! command -v cc >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! command -v g++ >/dev/null 2>&1 && ! command -v c++ >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if [ "$NEED_INSTALL" -eq 0 ]; then
        echo "[INFO] Dependencies already installed, skip install."
        return 0
    fi

    echo "[INFO] Missing dependencies detected, installing..."

    if [ -f /etc/redhat-release ]; then
        echo "[INFO] Detected RHEL/CentOS/Rocky/Alma"

        yum install -y epel-release || true
        yum install -y git gcc gcc-c++ make python3 python3-pip python3-openpyxl || true

        if ! python3 - << 'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    elif [ -f /etc/debian_version ]; then
        echo "[INFO] Detected Debian/Ubuntu"

        apt update
        apt install -y git build-essential python3 python3-pip python3-openpyxl

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

# ===== CUDA_HOME 自动检测（解决非交互 SSH 找不到 nvcc） =====
# 非交互 SSH（Paramiko）不加载 ~/.bashrc / ~/.bash_profile，
# 导致 command -v nvcc 找不到，即使 CUDA Toolkit 已安装。
# 此函数先查 PATH，再扫常见安装路径，找到后 export PATH / LD_LIBRARY_PATH。
find_cuda_home() {
    # 1) 先试 PATH（交互式登录或已加载 profile 的场景）
    if command -v nvcc >/dev/null 2>&1; then
        local nvcc_path
        nvcc_path=$(command -v nvcc)
        CUDA_HOME=$(cd "$(dirname "$nvcc_path")/.." && pwd)
        echo "[INFO] nvcc found in PATH: $nvcc_path"
        echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
        export CUDA_HOME
        export PATH="$CUDA_HOME/bin:$PATH"
        export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
        echo "[INFO] nvcc version: $(nvcc --version | grep release | sed -E 's/.*V([0-9.]+).*/\1/')"
        return 0
    fi

    # 2) 扫常见 CUDA 安装路径（非交互 SSH 的主要修复路径）
    for dir in /usr/local/cuda /usr/local/cuda-13.0 /usr/local/cuda-12.8 /usr/local/cuda-12.6 /usr/local/cuda-12.4 /usr/local/cuda-12.2; do
        if [ -x "$dir/bin/nvcc" ]; then
            CUDA_HOME="$dir"
            echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
            echo "[INFO] nvcc path: $CUDA_HOME/bin/nvcc"
            export CUDA_HOME
            export PATH="$CUDA_HOME/bin:$PATH"
            export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
            echo "[INFO] nvcc version: $(nvcc --version | grep release | sed -E 's/.*V([0-9.]+).*/\1/')"
            return 0
        fi
    done

    # 3) 兜底 glob：扫 /usr/local/cuda-* 下所有未知版本
    for dir in /usr/local/cuda-*; do
        if [ -d "$dir" ] && [ -x "$dir/bin/nvcc" ]; then
            CUDA_HOME="$dir"
            echo "[INFO] CUDA_HOME detected: $CUDA_HOME"
            echo "[INFO] nvcc path: $CUDA_HOME/bin/nvcc"
            export CUDA_HOME
            export PATH="$CUDA_HOME/bin:$PATH"
            export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
            echo "[INFO] nvcc version: $(nvcc --version | grep release | sed -E 's/.*V([0-9.]+).*/\1/')"
            return 0
        fi
    done

    echo "[WARN] CUDA_HOME not found via PATH or common paths."
    echo "[WARN] nvcc not found — CUDA Toolkit may not be installed."
    return 1
}

DURATION=${1:-43200}
INTERVAL=${2:-2}
TIME_TAG=$(date +%F_%H%M%S)

WORKDIR=$(pwd)
GPU_BURN_DIR="/opt/software/gpu-burn"
GPU_BURN="${GPU_BURN_DIR}/gpu_burn"

BURN_LOG="${WORKDIR}/stress_gpu_${TIME_TAG}.log"
MON_LOG="${WORKDIR}/gpu_monitor_${TIME_TAG}.csv"
REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.txt"
XLSX_REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.xlsx"

FORCE_REBUILD=${FORCE_REBUILD:-0}

if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "ERROR: nvidia-smi not found"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found"
    exit 1
fi

python3 - << 'PYCHK'
try:
    import openpyxl
except Exception:
    raise SystemExit("ERROR: python3-openpyxl not found. Install: apt install -y python3-openpyxl")
PYCHK

# ==== GPU 环境检测 ====
NVIDIA_SMI_PATH=$(command -v nvidia-smi)
echo "[INFO] nvidia-smi path: $NVIDIA_SMI_PATH"

# 自动检测 CUDA_HOME，非交互式 SSH 也保证能找到 nvcc
find_cuda_home

if [ "$FORCE_REBUILD" = "1" ] || [ ! -x "$GPU_BURN" ]; then
    echo "[INFO] gpu-burn not found or force rebuild, start building..."

    if [ -f /etc/redhat-release ]; then
        yum install -y git gcc make wget unzip || true
    elif [ -f /etc/debian_version ]; then
        apt update
        apt install -y git build-essential wget unzip
    fi

    if ! command -v nvcc >/dev/null 2>&1; then
        echo "[ERROR] nvcc not found — CUDA Toolkit 未安装或路径异常，无法编译 gpu-burn"
        echo "[INFO] nvidia-smi 已检测到（NVIDIA 驱动正常），但 nvcc 未找到（CUDA 编译工具链缺失）"
        exit 1
    fi

    (
        mkdir -p /opt/software
        cd /opt/software || exit 1

        if [ "$FORCE_REBUILD" = "1" ]; then
            rm -rf gpu-burn gpu-burn-master gpu-burn-master.zip
        fi

        if [ ! -d gpu-burn ]; then

            echo "[INFO] Try download gpu-burn from CHFS..."

            if wget -T 30 -O gpu-burn-master.zip \
                "http://171.221.252.54:8573/chfs/shared/1%E7%BC%96%E8%AF%91%E5%99%A8/GPU/gpu-burn-master.zip"; then

                echo "[INFO] CHFS download success"

                if unzip -o gpu-burn-master.zip; then

                    if [ -d gpu-burn-master ]; then
                        mv gpu-burn-master gpu-burn
                    fi

                fi
            fi

            #
            # CHFS失败自动走GitHub
            #
            if [ ! -d gpu-burn ]; then

                echo "[WARN] CHFS download failed, fallback to GitHub..."

                git clone https://github.com/wilicc/gpu-burn.git gpu-burn || {
                    echo "[ERROR] GitHub clone failed"
                    exit 1
                }
            fi

        else
            echo "[INFO] gpu-burn source already exists, skip download"
        fi

        cd gpu-burn || exit 1

        [ -f Makefile ] || {
            echo "[ERROR] gpu-burn Makefile not found"
            exit 1
        }

        echo "[INFO] building gpu-burn..."

        GPU_CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -1 | tr -d '.')

        if [ -z "$GPU_CC" ]; then

            GPU_NAME_DETECT=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)

            case "$GPU_NAME_DETECT" in
                *V100*) GPU_CC="70" ;;
                *T4*) GPU_CC="75" ;;
                *A100*|*A30*) GPU_CC="80" ;;
                *A40*|*A10*|*RTX*30*) GPU_CC="86" ;;
                *L40*|*L20*|*RTX*40*) GPU_CC="89" ;;
                *H100*|*H200*) GPU_CC="90" ;;
                *B200*) GPU_CC="100" ;;
                *) GPU_CC="" ;;
            esac
        fi

        make clean || true

        if [ -n "$GPU_CC" ]; then

            echo "[INFO] Detected GPU Compute Capability: ${GPU_CC}"

            make COMPUTE="${GPU_CC}" -j"$(nproc)" || {
                echo "[ERROR] make COMPUTE=${GPU_CC} failed"
                exit 1
            }

        else

            echo "[WARN] Cannot detect GPU Compute Capability, fallback to default make"

            make -j"$(nproc)" || {
                echo "[ERROR] make failed"
                exit 1
            }
        fi
    )

    if [ ! -x "$GPU_BURN" ]; then
        echo "[ERROR] gpu-burn build failed: $GPU_BURN"
        exit 1
    fi

    echo "[INFO] gpu-burn build success"
fi


if command -v nvcc >/dev/null 2>&1; then
    CUDA_TOOLKIT=$(nvcc --version | grep release | sed -E 's/.*V([0-9.]+).*/\1/')
else
    CUDA_TOOLKIT="Not Found"
fi

CUDA_DRIVER=$(nvidia-smi | grep -oE 'CUDA Version: [0-9.]+' | awk '{print $3}' | head -1)

GPU_INFO=$(nvidia-smi --query-gpu=index,name,driver_version,memory.total,power.limit --format=csv,noheader,nounits | head -1)

GPU_INDEX=$(echo "$GPU_INFO" | awk -F',' '{print $1}' | xargs)
GPU_NAME=$(echo "$GPU_INFO" | awk -F',' '{print $2}' | xargs)
DRIVER_VERSION=$(echo "$GPU_INFO" | awk -F',' '{print $3}' | xargs)
MEM_TOTAL=$(echo "$GPU_INFO" | awk -F',' '{print $4}' | xargs)
POWER_LIMIT=$(echo "$GPU_INFO" | awk -F',' '{print $5}' | xargs)


echo "======================================"
echo "GPU Stress Test Start"
echo "GPU      : ${GPU_NAME}"
echo "Duration : ${DURATION}s"
echo "Workdir  : ${WORKDIR}"
echo "Burn Dir : ${GPU_BURN_DIR}"
echo "======================================"

nvidia-smi \
--query-gpu=timestamp,index,name,utilization.gpu,temperature.gpu,power.draw,memory.used \
--format=csv -l "$INTERVAL" > "$MON_LOG" &

MON_PID=$!
sleep 2

set +e
(
  cd "$GPU_BURN_DIR" || exit 1
  ./gpu_burn "$DURATION"
) 2>&1 | tee "$BURN_LOG"
BURN_EXIT=${PIPESTATUS[0]}
set -e

kill "$MON_PID" >/dev/null 2>&1 || true
sleep 1

echo
echo "======================================"
echo "压测完成，压测报告生成中..."
echo "请勿按 Ctrl+C，等待 Report 文件生成"
echo "======================================"
echo

ERROR_COUNT=$(grep -E "errors:" "$BURN_LOG" | awk '{for(i=1;i<=NF;i++){if($i=="errors:"){print $(i+1)}}}' | sort -nr | head -1)
ERROR_COUNT=${ERROR_COUNT:-0}

GFLOPS_AVG=$(grep -oE '[0-9]+ Gflop/s' "$BURN_LOG" | awk '{sum+=$1; n++} END{if(n>0) printf "%.2f", sum/n; else print "0"}')
GFLOPS_MIN=$(grep -oE '[0-9]+ Gflop/s' "$BURN_LOG" | awk 'NR==1{min=$1+0} {v=$1+0; if(v<min)min=v} END{if(min!="") print min; else print "0"}')
GFLOPS_MAX=$(grep -oE '[0-9]+ Gflop/s' "$BURN_LOG" | awk 'NR==1{max=$1+0} {v=$1+0; if(v>max)max=v} END{if(max!="") print max; else print "0"}')

GPU_ERROR=$(grep -Ei "cuda error|failed|xid|fallen off|couldn't init|named symbol not found|read.*error|died|no clients are alive|aborting|error in" "$BURN_LOG" || true)

DATA_LINES=$(tail -n +2 "$MON_LOG" | grep -v "^$" || true)

ACTIVE_LINES=$(echo "$DATA_LINES" | awk -F',' '
{
    u=$4; p=$6; m=$7;
    gsub(/[^0-9.]/,"",u);
    gsub(/[^0-9.]/,"",p);
    gsub(/[^0-9.]/,"",m);
    if ((u+0) >= 90 || (p+0) >= 200 || (m+0) > 0) print $0
}')

if [ -z "$ACTIVE_LINES" ]; then
    ACTIVE_LINES="$DATA_LINES"
fi

UTIL_AVG=$(echo "$ACTIVE_LINES" | awk -F',' '{gsub(/[^0-9.]/,"",$4); sum+=$4+0; n++} END{if(n>0) printf "%.2f", sum/n; else print "0"}')
UTIL_MIN=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$4); min=$4+0} {gsub(/[^0-9.]/,"",$4); v=$4+0; if(v<min)min=v} END{print min+0}')
UTIL_MAX=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$4); max=$4+0} {gsub(/[^0-9.]/,"",$4); v=$4+0; if(v>max)max=v} END{print max+0}')

TEMP_AVG=$(echo "$ACTIVE_LINES" | awk -F',' '{gsub(/[^0-9.]/,"",$5); sum+=$5+0; n++} END{if(n>0) printf "%.2f", sum/n; else print "0"}')
TEMP_MIN=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$5); min=$5+0} {gsub(/[^0-9.]/,"",$5); v=$5+0; if(v<min)min=v} END{print min+0}')
TEMP_MAX=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$5); max=$5+0} {gsub(/[^0-9.]/,"",$5); v=$5+0; if(v>max)max=v} END{print max+0}')

POWER_AVG=$(echo "$ACTIVE_LINES" | awk -F',' '{gsub(/[^0-9.]/,"",$6); sum+=$6+0; n++} END{if(n>0) printf "%.2f", sum/n; else print "0"}')
POWER_MIN=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$6); min=$6+0} {gsub(/[^0-9.]/,"",$6); v=$6+0; if(v<min)min=v} END{print min+0}')
POWER_MAX=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$6); max=$6+0} {gsub(/[^0-9.]/,"",$6); v=$6+0; if(v>max)max=v} END{print max+0}')

MEM_AVG=$(echo "$ACTIVE_LINES" | awk -F',' '{gsub(/[^0-9.]/,"",$7); sum+=$7+0; n++} END{if(n>0) printf "%.2f", sum/n; else print "0"}')
MEM_MIN=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$7); min=$7+0} {gsub(/[^0-9.]/,"",$7); v=$7+0; if(v<min)min=v} END{print min+0}')
MEM_MAX=$(echo "$ACTIVE_LINES" | awk -F',' 'NR==1{gsub(/[^0-9.]/,"",$7); max=$7+0} {gsub(/[^0-9.]/,"",$7); v=$7+0; if(v>max)max=v} END{print max+0}')

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

if awk "BEGIN{exit !(${UTIL_MAX} < 90)}"; then
    RESULT="FAIL"
    REASON="GPU utilization did not reach expected full-load state."
fi

cat > "$REPORT" << EOR
GPU 稳定性压力测试报告

一、测试概述
本次测试针对 GPU 设备进行持续满载压力测试，主要验证设备在高负载状态下的计算稳定性、温度控制、功耗表现和运行可靠性。

二、测试对象
GPU Index              : ${GPU_INDEX}
GPU Model              : ${GPU_NAME}
Driver Version         : ${DRIVER_VERSION}
CUDA Version (Driver)  : ${CUDA_DRIVER}
CUDA Toolkit (nvcc)    : ${CUDA_TOOLKIT}
Total Memory           : ${MEM_TOTAL} MiB
Power Limit            : ${POWER_LIMIT} W

三、测试方法
测试工具              : gpu-burn
监控工具              : nvidia-smi
测试时长              : ${DURATION} 秒
采样间隔              : ${INTERVAL} 秒
压测程序目录          : ${GPU_BURN_DIR}
压测日志              : ${BURN_LOG}
监控日志              : ${MON_LOG}
Excel报告             : ${XLSX_REPORT}

四、测试结果汇总

1. 计算稳定性
平均算力              : ${GFLOPS_AVG} Gflop/s
最低算力              : ${GFLOPS_MIN} Gflop/s
最高算力              : ${GFLOPS_MAX} Gflop/s
计算错误              : ${ERROR_COUNT}
gpu-burn退出码        : ${BURN_EXIT}

2. GPU 负载
平均利用率            : ${UTIL_AVG} %
最低利用率            : ${UTIL_MIN} %
最高利用率            : ${UTIL_MAX} %

3. 温度表现
平均温度              : ${TEMP_AVG} °C
最低温度              : ${TEMP_MIN} °C
最高温度              : ${TEMP_MAX} °C

4. 功耗表现
平均功耗              : ${POWER_AVG} W
最低功耗              : ${POWER_MIN} W
最高功耗              : ${POWER_MAX} W

5. 显存使用
平均显存占用          : ${MEM_AVG} MiB
最低显存占用          : ${MEM_MIN} MiB
最高显存占用          : ${MEM_MAX} MiB

五、异常检查
gpu-burn errors        : ${ERROR_COUNT}
运行异常              : $( [ -z "$GPU_ERROR" ] && echo "未发现" || echo "发现异常，请查看压测日志" )

六、综合判定
测试结果              : ${RESULT}
判定原因              : ${REASON}

七、结论
$(if [ "$RESULT" = "PASS" ]; then
cat << PASS_TEXT
本次 GPU 压力测试期间，设备持续处于高负载运行状态，未发现计算错误、CUDA 错误、Xid 错误或设备掉线现象。GPU 利用率、温度、功耗和显存占用均处于稳定状态。

综合判断：该 GPU 在本次测试条件下运行稳定，满足高性能计算、AI 训练、推理服务等生产环境的稳定性要求。
PASS_TEXT
else
cat << FAIL_TEXT
本次 GPU 压力测试未通过。测试期间检测到异常或未达到有效满载状态。建议结合压测日志、nvidia-smi 监控日志、系统 dmesg 日志进一步排查 gpu-burn、CUDA环境、驱动、散热、供电或GPU硬件状态。
FAIL_TEXT
fi)

八、报告生成信息
报告生成时间          : $(date "+%F %T")
EOR

echo
echo "======================================"
echo "Excel 报告生成中..."
echo "======================================"

python3 - << PYEOF
import csv, re
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter

report = Path("${REPORT}")
burn_log = Path("${BURN_LOG}")
mon_log = Path("${MON_LOG}")
xlsx = Path("${XLSX_REPORT}")

result = "${RESULT}"
reason = "${REASON}"

wb = Workbook()
ws = wb.active
ws.title = "Summary"
raw = wb.create_sheet("RawReport")
burn = wb.create_sheet("BurnLog")
mon = wb.create_sheet("MonitorCSV")

dark = "1F4E78"
blue = "D9EAF7"
green = "C6EFCE"
red = "FFC7CE"
gray = "F2F2F2"
white = "FFFFFF"
border = Border(left=Side(style="thin", color="D9D9D9"),
                right=Side(style="thin", color="D9D9D9"),
                top=Side(style="thin", color="D9D9D9"),
                bottom=Side(style="thin", color="D9D9D9"))

ws.merge_cells("A1:H1")
ws["A1"] = "GPU 稳定性压力测试报告"
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
        ws.cell(row=row, column=col).border = border
        ws.cell(row=row, column=col).alignment = Alignment(vertical="center")
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=gray)
    ws.cell(row=row, column=1).font = Font(bold=True)
    return row + 1

r = 3
r = section(r, "一、测试对象")
for k, v in [
    ("GPU Index", "${GPU_INDEX}"),
    ("GPU Model", "${GPU_NAME}"),
    ("Driver Version", "${DRIVER_VERSION}"),
    ("CUDA Version (Driver)", "${CUDA_DRIVER}"),
    ("CUDA Toolkit (nvcc)", "${CUDA_TOOLKIT}"),
    ("Total Memory", "${MEM_TOTAL} MiB"),
    ("Power Limit", "${POWER_LIMIT} W"),
]:
    r = kv(r, k, v)

r += 1
r = section(r, "二、测试方法")
for k, v in [
    ("测试工具", "gpu-burn"),
    ("监控工具", "nvidia-smi"),
    ("测试时长", "${DURATION} 秒"),
    ("采样间隔", "${INTERVAL} 秒"),
    ("压测程序目录", "${GPU_BURN_DIR}"),
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

rows = [
    ("计算稳定性", "平均算力", "${GFLOPS_AVG} Gflop/s"),
    ("计算稳定性", "最低算力", "${GFLOPS_MIN} Gflop/s"),
    ("计算稳定性", "最高算力", "${GFLOPS_MAX} Gflop/s"),
    ("计算稳定性", "计算错误", "${ERROR_COUNT}"),
    ("GPU负载", "平均利用率", "${UTIL_AVG} %"),
    ("GPU负载", "最低利用率", "${UTIL_MIN} %"),
    ("GPU负载", "最高利用率", "${UTIL_MAX} %"),
    ("温度表现", "平均温度", "${TEMP_AVG} °C"),
    ("温度表现", "最低温度", "${TEMP_MIN} °C"),
    ("温度表现", "最高温度", "${TEMP_MAX} °C"),
    ("功耗表现", "平均功耗", "${POWER_AVG} W"),
    ("功耗表现", "最低功耗", "${POWER_MIN} W"),
    ("功耗表现", "最高功耗", "${POWER_MAX} W"),
    ("显存使用", "平均显存占用", "${MEM_AVG} MiB"),
    ("显存使用", "最低显存占用", "${MEM_MIN} MiB"),
    ("显存使用", "最高显存占用", "${MEM_MAX} MiB"),
]
for row in rows:
    for c, v in enumerate(row, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.border = border
        cell.alignment = Alignment(vertical="center")
    r += 1

r += 1
r = section(r, "四、综合判定")
r = kv(r, "测试结果", result)
ws.cell(row=r-1, column=2).fill = PatternFill("solid", fgColor=green if result == "PASS" else red)
ws.cell(row=r-1, column=2).font = Font(bold=True)
r = kv(r, "判定原因", reason)
r = kv(r, "报告生成时间", "$(date "+%F %T")")

for col, width in {"A":18, "B":28, "C":22, "D":14, "E":14, "F":14, "G":14, "H":14}.items():
    ws.column_dimensions[col].width = width

if report.exists():
    for line in report.read_text(errors="ignore").splitlines():
        raw.append([line])
raw.column_dimensions["A"].width = 120

if burn_log.exists():
    for line in burn_log.read_text(errors="ignore").splitlines():
        burn.append([line])
burn.column_dimensions["A"].width = 120

def clean_number(v):
    s = re.sub(r"[^0-9.\\-]", "", str(v))
    try:
        return float(s)
    except Exception:
        return None

if mon_log.exists():
    with mon_log.open(errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader, 1):
            out = []
            for j, val in enumerate(row, 1):
                if idx > 1 and j in (4,5,6,7):
                    n = clean_number(val)
                    out.append(n if n is not None else val)
                else:
                    out.append(val.strip() if isinstance(val, str) else val)
            mon.append(out)

for sheet in [raw, burn, mon]:
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1:
        for cell in sheet[1]:
            cell.font = Font(bold=True, color=white)
            cell.fill = PatternFill("solid", fgColor=dark)

for col in range(1, mon.max_column + 1):
    mon.column_dimensions[get_column_letter(col)].width = 22

if mon.max_row > 2 and mon.max_column >= 7:
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

    add_chart("GPU 利用率(%)", 4, "J3")
    add_chart("GPU 温度(°C)", 5, "J18")
    add_chart("GPU 功耗(W)", 6, "J33")
    add_chart("显存占用(MiB)", 7, "J48")

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
echo "GPU Stress Test Finished"
echo "Result      : $RESULT"
echo "Reason      : $REASON"
echo "Burn Log    : $BURN_LOG"
echo "Monitor Log : $MON_LOG"
echo "Text Report : $REPORT"
echo "XLSX Report : $XLSX_REPORT"
echo "======================================"
