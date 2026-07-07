import re

from sqlalchemy.orm import Session

from app.core.report_summary import get_cached_report_summary
from app.core.task_state_resolver import resolve_final_status
from app.models.server import Server
from app.models.task import Task


def parse_task_duration_seconds(task: Task) -> int | None:
    if task.params and isinstance(task.params, dict):
        ds = task.params.get("duration_seconds")
        if isinstance(ds, int) and ds > 0:
            return ds
    if task.task_type == "stress" and task.command_preview:
        match = re.search(r"(\d+)", task.command_preview)
        if match:
            value = int(match.group(1))
            return value if value > 0 else None
    return None


def resolve_task_final_status(task: Task, db: Session) -> str:
    report_status: str | None = None
    try:
        cache = get_cached_report_summary(db, task.task_id)
        if cache and isinstance(cache.summary_json, dict):
            report_status = (cache.summary_json.get("report_status") or "UNKNOWN").upper()
        elif cache:
            report_status = (cache.report_status or "UNKNOWN").upper()
    except Exception:
        pass
    return resolve_final_status(task.status or "UNKNOWN", report_status)


def serialize_task_record(task: Task, db: Session) -> dict[str, object]:
    server = db.get(Server, task.server_id)
    return {
        "id": task.id,
        "task_id": task.task_id,
        "server_id": task.server_id,
        "server_name": server.name if server else None,
        "server_host": server.host if server else None,
        "script_id": task.script_id,
        "task_type": task.task_type,
        "file_path": task.file_path,
        "file_name": task.file_name,
        "display_category": task.display_category,
        "remote_work_dir": task.remote_work_dir,
        "command_preview": task.command_preview,
        "status": task.status,
        "batch_id": task.batch_id,
        "sequence_index": task.sequence_index,
        "depends_on_task_id": task.depends_on_task_id,
        "params": task.params,
        "start_time": task.start_time,
        "end_time": task.end_time,
        "exit_code": task.exit_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "duration_seconds": parse_task_duration_seconds(task),
        "final_status": resolve_task_final_status(task, db),
    }
