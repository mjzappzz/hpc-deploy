from __future__ import annotations

import re
from datetime import datetime
from threading import Lock, Thread
from typing import Any

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.task_diagnosis import diagnose_task_failure
from app.db.database import SessionLocal
from app.models.server import Server
from app.models.task import Task, TaskReportSummary
from app.models.task_log import TaskLog
from sqlalchemy.orm import Session

REPORT_STATUS_VALUES = {"PASS", "FAIL", "UNKNOWN"}
DIAGNOSIS_VERSION = 11
_REPORT_FAILURE_REASON_PATTERN = re.compile(r"^\s*(?:Reason|判定原因)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_CORRECTED_ECC_MCE_REASON = (
    "检测到可纠正 ECC 内存错误（MCE/CECC）；系统已纠正，但反复出现表示内存子系统存在风险。"
    "请检查 DIMM、内存通道、CPU 内存控制器、主板与固件。"
)

_VERIFIED_FAILURE_CATEGORIES = {
    "artifact_recovery_failed",
    "gpu_burn_source_missing",
    "package_manager_locked",
    "shell_unbound_variable",
    "gpu_kernel_image_unavailable",
    "stress_root_required",
    "stress_startup_marker_mismatch",
    "uncorrected_memory_hardware_error",
    "user_canceled",
    "user_canceled_remote_unreachable",
}

_SUMMARY_JOBS: set[str] = set()
_SUMMARY_JOBS_LOCK = Lock()


def extract_report_failure_reason(content: str) -> str | None:
    """Extract the producer's explicit reason without reinterpreting it."""
    for line in content.splitlines():
        match = _REPORT_FAILURE_REASON_PATTERN.match(line)
        if match:
            return match.group(1).strip()
    return None


def _is_generic_report_reason(reason: str) -> bool:
    return reason.strip().lower() in {
        "critical kernel error detected.",
        "hardware or system event detected; inspect the event log for the matched evidence.",
        "stress-ng reported real critical error.",
        "observed normal monitor data.",
    }


def _last_logged_report_reason(log_messages: list[str] | None) -> str | None:
    if not log_messages:
        return None
    for message in reversed(log_messages):
        match = _REPORT_FAILURE_REASON_PATTERN.match(message)
        if match:
            return match.group(1).strip()
    return None


def resolve_failure_reason(
    task_error_message: str | None,
    report_status: str,
    diagnosis: dict[str, Any],
    *,
    file_name: str | None = None,
    log_messages: list[str] | None = None,
) -> str | None:
    if report_status not in {"FAIL", "UNKNOWN"}:
        return None
    if report_status == "UNKNOWN" and diagnosis.get("category") == "completed":
        return None
    if report_status == "FAIL" and (file_name or "").rsplit("/", 1)[-1] == "cpu_mem_stress_report.sh":
        cpu_memory_reason = resolve_cpu_memory_event_failure_reason(log_messages or [])
        if cpu_memory_reason:
            return cpu_memory_reason
    report_reason = _last_logged_report_reason(log_messages)
    if report_status == "FAIL" and report_reason and not _is_generic_report_reason(report_reason):
        return report_reason
    if diagnosis.get("category") in _VERIFIED_FAILURE_CATEGORIES:
        conclusion = diagnosis.get("conclusion")
        if isinstance(conclusion, str) and conclusion.strip():
            return conclusion.strip()
    conclusion = diagnosis.get("conclusion")
    if (
        isinstance(task_error_message, str)
        and isinstance(conclusion, str)
        and task_error_message.strip()
        and conclusion.strip() == task_error_message.strip()
    ):
        return task_error_message.strip()
    if report_status == "FAIL" and report_reason and not _is_generic_report_reason(report_reason):
        return report_reason
    if report_status == "FAIL":
        return "压测未通过，未能从已回收日志确认具体根因，请查看任务日志与结果文件。"
    return "任务执行失败，未能从已回收日志确认具体根因，请查看任务日志与结果文件。"


def resolve_cpu_memory_event_failure_reason(log_messages: list[str]) -> str | None:
    """Return a specific CPU/memory report reason from verified task evidence."""
    text = "\n".join(log_messages).lower()
    has_mce = "mce:" in text or "machine check" in text
    if "cecc" in text or (has_mce and "corrected error, no action required" in text):
        return _CORRECTED_ECC_MCE_REASON
    if "unrecoverable ecc memory error" in text or "ue/uecc" in text:
        return "检测到不可纠正 ECC 内存错误（UE/UECC）；请立即停止关键业务并检查 DIMM、内存通道、CPU 内存控制器和主板事件日志。"
    if "out-of-memory event detected" in text:
        return "检测到内存耗尽（OOM）事件；请检查工作负载内存规模、可用内存和 Swap 策略。"
    if "thermal throttling detected" in text:
        return "检测到热节流或过热保护；请检查散热器、风扇、功耗限制和环境温度。"
    if "machine check hardware error detected" in text:
        return "检测到机器检查硬件错误（MCE）；请检查 CPU、内存子系统、供电和平台事件日志。"
    if "stress-ng reported real critical error" in text:
        return "stress-ng 报告执行或校验错误；请查看 stress-ng 日志中的具体错误行。"
    return None


def unknown_report_summary(task: Task, *, reason: str = "report summary not generated") -> dict[str, Any]:
    return {
        "report_status": "UNKNOWN",
        "failure_reason": reason,
        "diagnosis": {
            "level": "info",
            "category": "report_not_ready",
            "attribution": "platform",
            "title": "报告摘要未就绪",
            "conclusion": "报告摘要缓存尚未生成。",
            "summary": reason,
            "possible_causes": ["历史任务尚未完成摘要回填", "任务刚结束，后台摘要生成尚未完成"],
            "suggestions": ["稍后刷新诊断结果", "如任务已完成较久仍无摘要，请检查任务日志和 artifacts"],
            "risk_tips": [],
            "matched_patterns": [],
            "evidence": [],
        },
    }


def get_cached_report_summary(db: Session, task_id: str) -> TaskReportSummary | None:
    return db.query(TaskReportSummary).filter(TaskReportSummary.task_id == task_id).first()


def _read_diagnosis_artifact_logs(task_id: str) -> list[str]:
    """Read only hardware-error evidence from collected task artifacts."""
    artifact_dir = ARTIFACTS_DIR / task_id
    if not artifact_dir.is_dir():
        return []

    markers = ("hardware error", "machine check", "uncorrected", "uecc", "edac")
    critical_evidence: list[str] = []
    other_evidence: list[str] = []
    for path in sorted(artifact_dir.glob("*error*.log")):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[-65536:]
        except OSError:
            continue
        for line in content.splitlines():
            if any(marker in line.lower() for marker in markers):
                item = f"[artifact:{path.name}] {line}"
                if "uncorrected" in line.lower() or "uecc" in line.lower():
                    critical_evidence.append(item)
                else:
                    other_evidence.append(item)
    gpu_markers = ("no kernel image", "couldn't init a gpu test", "no clients are alive", "cuda error", "xid")
    gpu_evidence: list[str] = []
    for path in sorted(artifact_dir.glob("stress_gpu*.log")):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[-65536:]
        except OSError:
            continue
        for line in content.splitlines():
            if any(marker in line.lower() for marker in gpu_markers):
                gpu_evidence.append(f"[artifact:{path.name}] {line}")
    return (critical_evidence + gpu_evidence + other_evidence)[:100]


def upsert_report_summary(
    db: Session,
    *,
    task: Task,
    report_status: str,
    failure_reason: str | None,
    summary_json: dict[str, Any],
) -> TaskReportSummary:
    if report_status not in REPORT_STATUS_VALUES:
        report_status = "UNKNOWN"

    row = get_cached_report_summary(db, task.task_id)
    if row is None:
        row = TaskReportSummary(task_id=task.task_id)
        db.add(row)

    row.batch_id = task.batch_id
    row.report_status = report_status
    row.failure_reason = failure_reason
    row.summary_json = summary_json
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def generate_report_summary(task_id: str) -> TaskReportSummary | None:
    """Generate lightweight cached report summary.

    This function may do local file/log reads and rule evaluation. It must be
    called from background/task completion paths, never from UI view endpoints.
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None:
            return None

        host = db.query(Server).with_entities(Server.host).filter(Server.id == task.server_id).scalar() or "?"

        log_rows = (
            db.query(TaskLog)
            .filter(TaskLog.task_id == task_id)
            .order_by(TaskLog.id.asc())
            .all()
        )
        log_messages = [row.message for row in log_rows] if log_rows else []
        log_messages.extend(_read_diagnosis_artifact_logs(task_id))
        if not log_messages and task.error_message:
            log_messages = [task.error_message]

        artifacts_present = False
        report_result: str | None = None
        report_failure_reason: str | None = None
        try:
            artifact_dir = ARTIFACTS_DIR / task_id
            if artifact_dir.is_dir():
                artifacts_present = any(
                    item.is_file() and item.suffix.lower() in {".xlsx", ".txt", ".csv", ".json", ".log"}
                    for item in artifact_dir.iterdir()
                )
                txt_reports = list(artifact_dir.glob("*report*.txt"))
                if txt_reports:
                    content = txt_reports[0].read_text(errors="replace", encoding="utf-8")
                    if "测试结果              : PASS" in content:
                        report_result = "PASS"
                    elif "测试结果              : FAIL" in content:
                        report_result = "FAIL"
                        report_failure_reason = extract_report_failure_reason(content)
        except Exception:
            artifacts_present = False
            report_result = None

        if report_failure_reason:
            log_messages.append(f"判定原因: {report_failure_reason}")

        diagnosis = diagnose_task_failure(
            task_status=task.status,
            error_message=task.error_message,
            logs=log_messages,
            exit_code=task.exit_code,
            task_type=task.task_type,
            server_name=host,
            file_name=task.file_name,
            params=task.params,
            start_time=task.start_time,
            end_time=task.end_time,
            batch_id=task.batch_id,
            artifacts_present=artifacts_present,
            report_result=report_result,
        )
        report_status = report_result or "UNKNOWN"
        failure_reason = resolve_failure_reason(
            task.error_message,
            report_status,
            diagnosis,
            file_name=task.file_name,
            log_messages=log_messages,
        )
        summary_json = {
            "diagnosis_version": DIAGNOSIS_VERSION,
            "report_status": report_status,
            "failure_reason": failure_reason,
            "artifacts_present": artifacts_present,
            "diagnosis": diagnosis,
        }
        return upsert_report_summary(
            db,
            task=task,
            report_status=report_status,
            failure_reason=failure_reason,
            summary_json=summary_json,
        )
    finally:
        db.close()


def schedule_report_summary_generation(task_id: str) -> None:
    with _SUMMARY_JOBS_LOCK:
        if task_id in _SUMMARY_JOBS:
            return
        _SUMMARY_JOBS.add(task_id)

    def _run() -> None:
        try:
            generate_report_summary(task_id)
        finally:
            with _SUMMARY_JOBS_LOCK:
                _SUMMARY_JOBS.discard(task_id)

    Thread(target=_run, name=f"report-summary-{task_id}", daemon=True).start()


def backfill_missing_report_summaries(limit: int = 500) -> int:
    """Generate summaries for terminal historical tasks missing cache rows."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Task.task_id, TaskReportSummary.summary_json)
            .outerjoin(TaskReportSummary, TaskReportSummary.task_id == Task.task_id)
            .filter(Task.status.in_(("SUCCESS", "FAILED", "CANCELED")))
            .order_by(Task.end_time.desc().nullslast(), Task.id.desc())
            .limit(limit)
            .all()
        )
        task_ids = [
            task_id
            for task_id, summary_json in rows
            if not isinstance(summary_json, dict)
            or int(summary_json.get("diagnosis_version", 0) or 0) < DIAGNOSIS_VERSION
        ]
    finally:
        db.close()

    for task_id in task_ids:
        generate_report_summary(task_id)
    return len(task_ids)


def backfill_stress_report_failure_summaries(limit: int = 500) -> int:
    """Refresh cached FAIL summaries for GPU, CPU/memory, and disk reports."""
    stress_scripts = ("gpu_stress_report.sh", "cpu_mem_stress_report.sh", "disk_stress_report.sh")
    db = SessionLocal()
    try:
        task_ids = [
            task_id
            for (task_id,) in (
                db.query(Task.task_id)
                .join(TaskReportSummary, TaskReportSummary.task_id == Task.task_id)
                .filter(Task.file_name.in_(stress_scripts), TaskReportSummary.report_status == "FAIL")
                .order_by(Task.end_time.desc().nullslast(), Task.id.desc())
                .limit(limit)
                .all()
            )
        ]
    finally:
        db.close()

    for task_id in task_ids:
        generate_report_summary(task_id)
    return len(task_ids)


def schedule_missing_report_summary_backfill(limit: int = 500) -> None:
    def _run() -> None:
        backfill_missing_report_summaries(limit=limit)

    Thread(target=_run, name="report-summary-backfill", daemon=True).start()
