import re

from sqlalchemy.orm import Session

from app.core.report_summary import get_cached_report_summary
from app.core.task_state_resolver import resolve_final_status
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog


def normalize_success_skip_message(message: str) -> str | None:
    text = re.sub(r"^\[[A-Z]+\]\s*", "", message.strip())
    if "无需锁定系统版本" in text:
        return text
    if text == "nvidia-smi is available; skipping NVIDIA driver installation":
        return "检测到 nvidia-smi 可用，已跳过 NVIDIA 驱动安装"
    match = re.fullmatch(r"CUDA Toolkit ([0-9.]+) is already installed; skipping", text)
    if match:
        return f"CUDA Toolkit {match.group(1)} 已安装，已跳过安装"
    return None


def resolve_success_outcome_message(file_name: str | None, messages: list[str]) -> str | None:
    normalized_messages = [re.sub(r"^\[[A-Z]+\]\s*", "", message.strip()) for message in messages]

    for message in normalized_messages:
        normalized = normalize_success_skip_message(message)
        if normalized:
            return normalized

    script_name = (file_name or "").rsplit("/", 1)[-1]
    message_text = "\n".join(normalized_messages)
    if script_name == "install_oneapi_2022.sh" and all(
        marker in message_text
        for marker in (
            "BaseKit 目标组件已安装，跳过安装",
            "HPCKit 目标组件已安装，跳过安装",
        )
    ):
        return "Intel oneAPI 2022 目标组件原已安装，本次未重复安装，仅完成验证"

    if script_name == "install_openmpi_4.1.6_aocc_aocl.sh" and all(
        marker in message_text
        for marker in (
            "AOCC 已安装，跳过安装",
            "AOCL 已安装，跳过安装",
            "OpenMPI 4.1.6 已安装，跳过编译",
        )
    ):
        return "AOCC、AOCL、OpenMPI 4.1.6 原已安装，本次未重复安装，仅完成验证"

    return None


def resolve_card_outcome_title(
    *,
    task_type: str | None,
    report_status: str,
    diagnosis: dict | None,
    fallback: str | None,
) -> str | None:
    """Return a compact, evidence-backed card label without replacing details."""
    title = diagnosis.get("title") if isinstance(diagnosis, dict) else None
    if isinstance(title, str) and title.strip() and title not in {"任务执行成功", "未知失败类型"}:
        return title.strip()
    if report_status.upper() == "FAIL":
        return "GPU 压测报告未通过" if task_type == "stress" else "任务报告未通过"
    return fallback


def get_task_card_outcome_title(
    task: Task,
    db: Session,
    *,
    failure_reason: str | None,
    report_status: str,
) -> str | None:
    diagnosis: dict | None = None
    try:
        cache = get_cached_report_summary(db, task.task_id)
        if cache and isinstance(cache.summary_json, dict):
            value = cache.summary_json.get("diagnosis")
            diagnosis = value if isinstance(value, dict) else None
    except Exception:
        diagnosis = None
    return resolve_card_outcome_title(
        task_type=task.task_type,
        report_status=report_status,
        diagnosis=diagnosis,
        fallback=failure_reason or task.error_message,
    )


def get_task_outcome_message(task: Task, db: Session, failure_reason: str | None) -> str | None:
    status = (task.status or "").upper()
    if status in {"FAILED", "CANCELED", "TIMEOUT"} or failure_reason:
        return failure_reason or task.error_message
    if status != "SUCCESS":
        return None
    logs = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task.task_id,
            (
                TaskLog.message.contains("无需锁定系统版本")
                | TaskLog.message.contains("skipping NVIDIA driver installation")
                | TaskLog.message.contains("is already installed; skipping")
                | TaskLog.message.contains("BaseKit 目标组件已安装，跳过安装")
                | TaskLog.message.contains("HPCKit 目标组件已安装，跳过安装")
                | TaskLog.message.contains("AOCC 已安装，跳过安装")
                | TaskLog.message.contains("AOCL 已安装，跳过安装")
                | TaskLog.message.contains("OpenMPI 4.1.6 已安装，跳过编译")
            ),
        )
        .order_by(TaskLog.id.asc())
        .all()
    )
    return resolve_success_outcome_message(task.file_name, [log.message for log in logs])


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


def get_task_report_fields(task: Task, db: Session) -> tuple[str, str, str | None]:
    report_status: str = "UNKNOWN"
    failure_reason: str | None = None
    try:
        cache = get_cached_report_summary(db, task.task_id)
        if cache and isinstance(cache.summary_json, dict):
            report_status = (cache.summary_json.get("report_status") or "UNKNOWN").upper()
            failure_reason = cache.summary_json.get("failure_reason") or cache.failure_reason
        elif cache:
            report_status = (cache.report_status or "UNKNOWN").upper()
            failure_reason = cache.failure_reason
    except Exception:
        pass
    final_status = resolve_final_status(task.status or "UNKNOWN", report_status)
    return final_status, report_status, failure_reason


def resolve_task_final_status(task: Task, db: Session) -> str:
    final_status, _report_status, _failure_reason = get_task_report_fields(task, db)
    return final_status


def serialize_task_record(task: Task, db: Session) -> dict[str, object]:
    server = db.get(Server, task.server_id)
    final_status, report_status, failure_reason = get_task_report_fields(task, db)
    return {
        "id": task.id,
        "task_id": task.task_id,
        "server_id": task.server_id,
        "server_name": server.name if server else None,
        "server_host": server.host if server else None,
        "server_username": server.username if server else None,
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
        "final_status": final_status,
        "report_status": report_status,
        "failure_reason": failure_reason,
        "outcome_message": get_task_outcome_message(task, db, failure_reason),
        "outcome_title": get_task_card_outcome_title(
            task,
            db,
            failure_reason=failure_reason,
            report_status=report_status,
        ),
    }
