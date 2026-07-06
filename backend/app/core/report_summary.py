from __future__ import annotations

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

_SUMMARY_JOBS: set[str] = set()
_SUMMARY_JOBS_LOCK = Lock()


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
        if not log_messages and task.error_message:
            log_messages = [task.error_message]

        artifacts_present = False
        report_result: str | None = None
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
        except Exception:
            artifacts_present = False
            report_result = None

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
        failure_reason = task.error_message if report_status in {"FAIL", "UNKNOWN"} else None
        summary_json = {
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
            db.query(Task.task_id)
            .outerjoin(TaskReportSummary, TaskReportSummary.task_id == Task.task_id)
            .filter(
                Task.status.in_(("SUCCESS", "FAILED", "CANCELED")),
                TaskReportSummary.task_id.is_(None),
            )
            .order_by(Task.end_time.desc().nullslast(), Task.id.desc())
            .limit(limit)
            .all()
        )
        task_ids = [row[0] for row in rows]
    finally:
        db.close()

    for task_id in task_ids:
        generate_report_summary(task_id)
    return len(task_ids)


def schedule_missing_report_summary_backfill(limit: int = 500) -> None:
    def _run() -> None:
        backfill_missing_report_summaries(limit=limit)

    Thread(target=_run, name="report-summary-backfill", daemon=True).start()
