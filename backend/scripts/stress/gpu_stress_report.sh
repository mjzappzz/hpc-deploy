#!/usr/bin/env bash

set -u
set -o pipefail

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
#
# 特点：
#   1. gpu-burn 默认压测所有可见 NVIDIA GPU
#   2. nvidia-smi 监控所有 GPU
#   3. XLSX 按 GPU index 分别统计利用率、温度、功耗、显存
#   4. 修复原脚本只显示第一张卡、功耗混算的问题
# ============================================================

DURATION="${1:-43200}"
INTERVAL="${2:-2}"
TIME_TAG="$(date +%F_%H%M%S)"

WORKDIR="$(pwd)"
GPU_BURN_DIR="/opt/software/gpu-burn"
GPU_BURN="${GPU_BURN_DIR}/gpu_burn"

BURN_LOG="${WORKDIR}/stress_gpu_${TIME_TAG}.log"
MON_LOG="${WORKDIR}/gpu_monitor_${TIME_TAG}.csv"
GPU_META_CSV="${WORKDIR}/gpu_metadata_${TIME_TAG}.csv"
REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.txt"
XLSX_REPORT="${WORKDIR}/gpu_stress_report_${TIME_TAG}.xlsx"

FORCE_REBUILD="${FORCE_REBUILD:-0}"

log() {
    echo "$(date '+%F %T') $*"
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

    NEED_INSTALL=0

    for cmd in python3 make git; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            NEED_INSTALL=1
        fi
    done

    if ! command -v gcc >/dev/null 2>&1 && ! command -v cc >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! command -v g++ >/dev/null 2>&1 && ! command -v c++ >/dev/null 2>&1; then
        NEED_INSTALL=1
    fi

    if ! python3 - <<'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
    then
        NEED_INSTALL=1
    fi

    if [ "$NEED_INSTALL" -eq 0 ]; then
        echo "[INFO] Dependencies already installed, skip install."
        return 0
    fi

    echo "[INFO] Missing dependencies detected, installing..."

    if [ -f /etc/redhat-release ]; then
        yum install -y epel-release || true
        yum install -y git gcc gcc-c++ make wget unzip python3 python3-pip python3-openpyxl || true

        if ! python3 - <<'PYCHK' >/dev/null 2>&1
import openpyxl
PYCHK
        then
            python3 -m pip install openpyxl
        fi

    elif [ -f /etc/debian_version ]; then
        apt update
        apt install -y git build-essential wget unzip python3 python3-pip python3-openpyxl

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

    if [ "$FORCE_REBUILD" != "1" ] && [ -x "$GPU_BURN" ]; then
        echo "[INFO] gpu-burn already exists: $GPU_BURN"
        return 0
    fi

    echo "[INFO] gpu-burn not found or force rebuild, start building..."

    if ! command -v nvcc >/dev/null 2>&1; then
        echo "[ERROR] nvcc not found，无法编译 gpu-burn"
        echo "[INFO] nvidia-smi 存在说明驱动正常，但缺 CUDA Toolkit / nvcc"
        exit 1
    fi

    if [ -f /etc/redhat-release ]; then
        yum install -y git gcc gcc-c++ make wget unzip || true
    elif [ -f /etc/debian_version ]; then
        apt update
        apt install -y git build-essential wget unzip
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
                "http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/gpu-burn-master.zip"; then

                echo "[INFO] CHFS download success"

                if unzip -o gpu-burn-master.zip; then
                    if [ -d gpu-burn-master ]; then
                        mv gpu-burn-master gpu-burn
                    fi
                fi
            fi

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

        if [ ! -f Makefile ]; then
            echo "[ERROR] gpu-burn Makefile not found"
            exit 1
        fi

        echo "[INFO] building gpu-burn..."

        make clean || true

        COMPUTE_LIST="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | sed 's/\.//g' | sort -u | xargs || true)"
        COMPUTE_COUNT="$(echo "$COMPUTE_LIST" | awk '{print NF}')"

        if [ "$COMPUTE_COUNT" = "1" ] && [ -n "$COMPUTE_LIST" ]; then
            echo "[INFO] Single GPU compute capability detected: ${COMPUTE_LIST}"
            make COMPUTE="${COMPUTE_LIST}" -j"$(nproc)" || {
                echo "[ERROR] make COMPUTE=${COMPUTE_LIST} failed"
                exit 1
            }
        else
            echo "[WARN] Multiple or unknown compute capabilities: ${COMPUTE_LIST:-unknown}"
            echo "[WARN] Use gpu-burn default Makefile build."
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

    echo "[INFO] gpu-burn build success: $GPU_BURN"
}

main() {
    install_deps

    echo "======================================"
    echo "GPU Stress Test Start"
    echo "Duration : ${DURATION}s"
    echo "Interval : ${INTERVAL}s"
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

    CUDA_DRIVER="$(nvidia-smi | grep -oE 'CUDA Version: [0-9.]+' | awk '{print $3}' | head -1 || true)"
    NVIDIA_SMI_PATH="$(command -v nvidia-smi || true)"

    echo "[INFO] nvidia-smi path: ${NVIDIA_SMI_PATH}"
    echo "[INFO] CUDA Driver Version: ${CUDA_DRIVER:-Unknown}"
    echo "[INFO] CUDA Toolkit Version: ${CUDA_TOOLKIT:-Unknown}"

    echo "[INFO] Start monitoring all GPUs..."
    nvidia-smi \
        --query-gpu=timestamp,index,name,utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total \
        --format=csv \
        -l "$INTERVAL" > "$MON_LOG" &

    MON_PID=$!
    sleep 2

    echo "[INFO] Start gpu-burn. It will stress all visible NVIDIA GPUs."
    set +e
    (
        cd "$GPU_BURN_DIR" || exit 1
        ./gpu_burn "$DURATION"
    ) 2>&1 | tee "$BURN_LOG"
    BURN_EXIT=${PIPESTATUS[0]}
    set -e

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

    export DURATION INTERVAL TIME_TAG WORKDIR GPU_BURN_DIR BURN_LOG MON_LOG GPU_META_CSV REPORT XLSX_REPORT
    export BURN_EXIT ERROR_COUNT RESULT REASON CUDA_TOOLKIT CUDA_DRIVER NVIDIA_SMI_PATH GPU_COUNT

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
cuda_driver = os.environ.get("CUDA_DRIVER", "")
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
lines.append(f"CUDA Version Driver   : {cuda_driver}")
lines.append(f"CUDA Toolkit nvcc     : {cuda_toolkit}")
lines.append(f"nvidia-smi            : {nvidia_smi_path}")
lines.append(f"测试时长              : {duration} 秒")
lines.append(f"采样间隔              : {interval} 秒")
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
    ("CUDA Version Driver", cuda_driver),
    ("CUDA Toolkit nvcc", cuda_toolkit),
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
