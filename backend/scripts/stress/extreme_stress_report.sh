#!/usr/bin/env bash
set -u
set -o pipefail

# Atomic GPU + CPU/memory stress coordinator. Child scripts are uploaded by the
# controller into this work directory and retain their normal report formats.
DURATION="${1:-43200}"
INTERVAL="${2:-2}"
GPU_TEMP_LIMIT_C="${HPCDEPLOY_EXTREME_GPU_TEMP_LIMIT_C:-90}"
GPU_TEMP_CONSECUTIVE_SAMPLES="${HPCDEPLOY_EXTREME_GPU_TEMP_CONSECUTIVE_SAMPLES:-3}"
SSH_FAILURE_THRESHOLD="${HPCDEPLOY_EXTREME_SSH_FAILURE_THRESHOLD:-3}"
WORKDIR="$(pwd)"
SYNC_DIR="${WORKDIR}/.extreme-sync"
RESULT_FILE="${WORKDIR}/extreme_stress_result.json"
GPU_DIR="${WORKDIR}/gpu"
CPU_DIR="${WORKDIR}/cpu_mem"
mkdir -p "$SYNC_DIR" "$GPU_DIR" "$CPU_DIR"

validate_positive_integer() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
    0) return 1 ;;
    *) return 0 ;;
  esac
}

if ! validate_positive_integer "$GPU_TEMP_LIMIT_C" || ! validate_positive_integer "$GPU_TEMP_CONSECUTIVE_SAMPLES" || ! validate_positive_integer "$SSH_FAILURE_THRESHOLD"; then
  echo "[ERROR] invalid extreme safety configuration: temperature limit, consecutive samples and SSH failure threshold must be positive integers"
  exit 2
fi

TEMPERATURE_MONITOR_STATUS="warning"
TEMPERATURE_MONITOR_SOURCE="unavailable"
GPU_TEMP_SAMPLE_C=""
sample_gpu_temperature() {
  local raw value
  command -v nvidia-smi >/dev/null 2>&1 || return 1
  raw="$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)" || return 1
  value="$(printf '%s\n' "$raw" | awk '
    /^[[:space:]]*[0-9]+([.][0-9]+)?[[:space:]]*$/ { if ($1 > max || !seen) max=$1; seen=1 }
    END { if (seen) print max }
  ')"
  [ -n "$value" ] || return 1
  GPU_TEMP_SAMPLE_C="$value"
  return 0
}

if sample_gpu_temperature; then
  TEMPERATURE_MONITOR_STATUS="pass"
  TEMPERATURE_MONITOR_SOURCE="nvidia-smi"
  echo "[INFO] temperature monitor ready source=${TEMPERATURE_MONITOR_SOURCE} sample=${GPU_TEMP_SAMPLE_C}C limit=${GPU_TEMP_LIMIT_C}C consecutive=${GPU_TEMP_CONSECUTIVE_SAMPLES}"
else
  echo "[WARN] temperature monitor unavailable; no temperature protection conclusion will be reported"
fi
printf '{"gpu_temperature_limit_c":%s,"gpu_temperature_consecutive_samples":%s,"ssh_failure_threshold":%s,"temperature_monitor":"%s","temperature_source":"%s"}\n' \
  "$GPU_TEMP_LIMIT_C" "$GPU_TEMP_CONSECUTIVE_SAMPLES" "$SSH_FAILURE_THRESHOLD" "$TEMPERATURE_MONITOR_STATUS" "$TEMPERATURE_MONITOR_SOURCE" > "$WORKDIR/extreme_stress_config.json"

gpu_pid=""; cpu_pid=""
STOP_REASON=""
STOP_TRIGGERED=0
STOP_CLEANUP_DONE=0
collect_module_artifacts() {
  local module_dir="$1" prefix="$2" artifact
  # The artifact collector intentionally downloads only the task root. Publish
  # child reports there so each module remains independently downloadable.
  for artifact in "$module_dir"/*.txt "$module_dir"/*.csv "$module_dir"/*.xlsx "$module_dir"/*.json "$module_dir"/*.log; do
    [ -f "$artifact" ] || continue
    cp "$artifact" "$WORKDIR/${prefix}_$(basename "$artifact")"
  done
}

stop_children() {
  [ "$STOP_CLEANUP_DONE" -eq 1 ] && return 0
  STOP_CLEANUP_DONE=1
  for pid in "$gpu_pid" "$cpu_pid"; do
    [ -n "$pid" ] && kill -TERM "-$pid" 2>/dev/null || true
  done
  sleep 2
  for pid in "$gpu_pid" "$cpu_pid"; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -KILL "-$pid" 2>/dev/null || true
  done
}

request_atomic_stop() {
  STOP_TRIGGERED=1
  STOP_REASON="${1:-operator cancellation}"
  stop_children
}

handle_signal() {
  request_atomic_stop "operator cancellation"
  exit 130
}

trap 'request_atomic_stop "coordinator cleanup"' EXIT
trap handle_signal INT TERM

prepare() {
  echo "[STAGE] dependency_check_start"
  (cd "$GPU_DIR" && HPCDEPLOY_EXTREME_PREPARE_ONLY=1 ../gpu_stress_report.sh "$DURATION" "$INTERVAL")
  (cd "$CPU_DIR" && HPCDEPLOY_EXTREME_PREPARE_ONLY=1 ../cpu_mem_stress_report.sh "$DURATION" "$INTERVAL")
  echo "[STAGE] dependency_check_done"
}

prepare

(cd "$GPU_DIR" && exec setsid env HPCDEPLOY_EXTREME_SYNC_DIR="$SYNC_DIR" ../gpu_stress_report.sh "$DURATION" "$INTERVAL") & gpu_pid=$!
(cd "$CPU_DIR" && exec setsid env HPCDEPLOY_EXTREME_SYNC_DIR="$SYNC_DIR" MEMORY_SAFETY_RESERVE_PERCENT=15 ../cpu_mem_stress_report.sh "$DURATION" "$INTERVAL") & cpu_pid=$!

deadline=$(( $(date +%s) + 600 ))
while [ ! -f "$SYNC_DIR/gpu.ready" ] || [ ! -f "$SYNC_DIR/cpu_mem.ready" ]; do
  if ! kill -0 "$gpu_pid" 2>/dev/null || ! kill -0 "$cpu_pid" 2>/dev/null || [ "$(date +%s)" -ge "$deadline" ]; then
    echo "[ERROR] extreme preparation did not reach both ready markers"
    exit 1
  fi
  sleep 0.05
done

echo "[STAGE] stress_start"
: > "$SYNC_DIR/start"
while [ ! -f "$SYNC_DIR/gpu.started" ] || [ ! -f "$SYNC_DIR/cpu_mem.started" ]; do sleep 0.05; done
gpu_start=$(cat "$SYNC_DIR/gpu.started"); cpu_start=$(cat "$SYNC_DIR/cpu_mem.started")
skew_ms=$(( (${gpu_start} - ${cpu_start}) / 1000000 )); [ "$skew_ms" -lt 0 ] && skew_ms=$(( -skew_ms ))
if [ "$skew_ms" -gt 2000 ]; then echo "[ERROR] extreme start skew ${skew_ms}ms exceeds 2000ms"; exit 1; fi
while kill -0 "$gpu_pid" 2>/dev/null && kill -0 "$cpu_pid" 2>/dev/null; do
  if [ -f "$SYNC_DIR/thermal.stop" ]; then
    request_atomic_stop "continuous GPU over-temperature threshold reached"
    break
  fi
  if [ -f "$SYNC_DIR/stop" ]; then
    request_atomic_stop "atomic stop requested"
    break
  fi
  sleep 1
done
if [ "$STOP_TRIGGERED" -eq 1 ]; then
  wait "$gpu_pid" 2>/dev/null || gpu_rc=$?
  wait "$cpu_pid" 2>/dev/null || cpu_rc=$?
  gpu_rc="${gpu_rc:-143}"
  cpu_rc="${cpu_rc:-143}"
  collect_module_artifacts "$GPU_DIR" "gpu"
  collect_module_artifacts "$CPU_DIR" "cpu_mem"
  printf '{"report_status":"FAIL","gpu_exit":%s,"cpu_mem_exit":%s,"start_skew_ms":%s,"reason":"%s"}\n' "$gpu_rc" "$cpu_rc" "$skew_ms" "$STOP_REASON" > "$RESULT_FILE"
  echo "[SUMMARY] Result: FAIL"
  echo "Reason: $STOP_REASON"
  echo "[STAGE] script_exit exit_code=1"
  exit 1
fi
if ! kill -0 "$cpu_pid" 2>/dev/null && kill -0 "$gpu_pid" 2>/dev/null; then
  wait "$cpu_pid"; cpu_rc=$?
  if [ "$cpu_rc" -ne 0 ]; then
    echo "[ERROR] CPU/memory module failed; stopping GPU peer."
    kill -TERM "-$gpu_pid" 2>/dev/null || true
  fi
  wait "$gpu_pid"; gpu_rc=$?
elif ! kill -0 "$gpu_pid" 2>/dev/null && kill -0 "$cpu_pid" 2>/dev/null; then
  wait "$gpu_pid"; gpu_rc=$?
  if [ "$gpu_rc" -ne 0 ]; then
    echo "[ERROR] GPU module failed; stopping CPU/memory peer."
    kill -TERM "-$cpu_pid" 2>/dev/null || true
  fi
  wait "$cpu_pid"; cpu_rc=$?
else
  wait "$gpu_pid"; gpu_rc=$?
  wait "$cpu_pid"; cpu_rc=$?
fi
collect_module_artifacts "$GPU_DIR" "gpu"
collect_module_artifacts "$CPU_DIR" "cpu_mem"
result=PASS; reason="GPU and CPU/memory stress passed with synchronized start."
if [ "$gpu_rc" -ne 0 ] || [ "$cpu_rc" -ne 0 ]; then result=FAIL; reason="GPU or CPU/memory stress failed."; fi
printf '{"report_status":"%s","gpu_exit":%s,"cpu_mem_exit":%s,"start_skew_ms":%s,"reason":"%s"}\n' "$result" "$gpu_rc" "$cpu_rc" "$skew_ms" "$reason" > "$RESULT_FILE"
echo "[SUMMARY] Result: $result"
echo "Reason: $reason"
echo "[STAGE] script_exit exit_code=$([ "$result" = PASS ] && echo 0 || echo 1)"
[ "$result" = PASS ]
