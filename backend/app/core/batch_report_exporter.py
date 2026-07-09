import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.artifact_collector import ARTIFACTS_DIR
from app.models.server import Server
from app.models.task import Task, TaskReportSummary
from sqlalchemy.orm import Session


@dataclass
class BatchReportZip:
    path: Path
    filename: str


def _safe_zip_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned.strip("._ ") or "unknown"


def _report_prefix(task: Task) -> str:
    file_name = (task.file_name or "").lower()
    if "gpu" in file_name:
        return "gpu_report"
    if "cpu" in file_name or "mem" in file_name:
        return "cpu_mem_report"
    if "disk" in file_name:
        return "disk_report"
    return "task_report"


REPORT_MODULE_ORDER = {
    "gpu_report": 1,
    "cpu_mem_report": 2,
    "disk_report": 3,
}


def _server_name_for_task(task: Task, servers_by_id: dict[int, Server], fallback: str) -> str:
    server = servers_by_id.get(task.server_id)
    if server and server.name:
        return server.name
    return fallback


def _iter_report_files(task_id: str) -> list[Path]:
    artifact_dir = ARTIFACTS_DIR / task_id
    if not artifact_dir.is_dir():
        return []
    reports: list[Path] = []
    for entry in sorted(artifact_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        if entry.suffix.lower() == ".xlsx" and "report" in entry.name.lower():
            reports.append(entry)
    return reports


def _report_archive_name(task: Task, report: Path, used_names: set[str], root_folder: str | None = None) -> str:
    prefix = _report_prefix(task)
    candidate_name = f"{prefix}{report.suffix.lower()}"
    candidate = f"{root_folder}/{candidate_name}" if root_folder else candidate_name
    index = 2
    while candidate in used_names:
        candidate_name = f"{prefix}_{index}{report.suffix.lower()}"
        candidate = f"{root_folder}/{candidate_name}" if root_folder else candidate_name
        index += 1
    used_names.add(candidate)
    return candidate


def _task_has_ok_report(task: Task, reports: list[Path], report_status_by_task: dict[str, str]) -> bool:
    if not reports:
        return False
    report_status = (report_status_by_task.get(task.task_id) or "").upper()
    if report_status == "PASS":
        return True
    if report_status == "FAIL":
        return False
    return (task.status or "").upper() == "SUCCESS"


def _select_latest_ok_tasks(server_tasks: list[Task], report_status_by_task: dict[str, str]) -> tuple[list[Task], list[str]]:
    grouped_by_module: dict[str, list[Task]] = {}
    for task in sorted(server_tasks, key=lambda item: (item.sequence_index or 999, item.id)):
        grouped_by_module.setdefault(_report_prefix(task), []).append(task)

    selected: list[Task] = []
    missing_lines: list[str] = []
    for module, module_tasks in grouped_by_module.items():
        chosen: Task | None = None
        for task in sorted(module_tasks, key=lambda item: (item.sequence_index or 0, item.id), reverse=True):
            reports = _iter_report_files(task.task_id)
            if _task_has_ok_report(task, reports, report_status_by_task):
                chosen = task
                break
        if chosen is not None:
            selected.append(chosen)
        else:
            latest = sorted(module_tasks, key=lambda item: (item.sequence_index or 0, item.id), reverse=True)[0]
            missing_lines.append(f"{latest.task_id} {latest.file_name or module}: ok xlsx report missing")
    selected.sort(key=lambda item: (REPORT_MODULE_ORDER.get(_report_prefix(item), 999), item.sequence_index or 999, item.id))
    return selected, missing_lines


def build_batch_report_zip(
    batch_id: str,
    tasks: list[Task],
    servers_by_id: dict[int, Server],
    report_status_by_task: dict[str, str] | None = None,
) -> BatchReportZip:
    if not tasks:
        raise ValueError("batch has no tasks")

    created_at = tasks[0].created_at or datetime.now()
    timestamp = created_at.strftime("%Y%m%d")
    fallback_server_name = f"{batch_id}_server"

    tmp = tempfile.NamedTemporaryFile(prefix=f"hpcdeploy-{batch_id}-", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        server_name = _server_name_for_task(task, servers_by_id, fallback_server_name)
        grouped.setdefault(server_name, []).append(task)

    single_server = len(grouped) == 1
    if single_server:
        server_name = next(iter(grouped.keys()))
        zip_filename = f"{_safe_zip_name(server_name)}_压测报告_{timestamp}.zip"
    else:
        zip_filename = f"{_safe_zip_name(batch_id)}.zip"

    with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        used_names: set[str] = set()
        missing_lines: list[str] = []
        report_statuses = report_status_by_task or {}
        for server_name, server_tasks in sorted(grouped.items(), key=lambda item: item[0]):
            root_folder = None if single_server else _safe_zip_name(server_name)
            selected_tasks, server_missing = _select_latest_ok_tasks(server_tasks, report_statuses)
            missing_lines.extend(f"{server_name} {line}" for line in server_missing)
            for task in selected_tasks:
                reports = _iter_report_files(task.task_id)
                for report in reports:
                    zf.write(report, _report_archive_name(task, report, used_names, root_folder))

        if missing_lines:
            missing_path = "missing.txt" if single_server else "_missing.txt"
            zf.writestr(missing_path, "\n".join(missing_lines) + "\n")

    return BatchReportZip(path=tmp_path, filename=zip_filename)


def export_batch_report_zip(db: Session, batch_id: str) -> BatchReportZip | None:
    tasks = (
        db.query(Task)
        .filter(Task.batch_id == batch_id)
        .order_by(Task.server_id.asc(), Task.sequence_index.asc().nulls_last(), Task.id.asc())
        .all()
    )
    if not tasks:
        return None

    server_ids = {task.server_id for task in tasks}
    servers = db.query(Server).filter(Server.id.in_(server_ids)).all() if server_ids else []
    servers_by_id = {server.id: server for server in servers}
    task_ids = [task.task_id for task in tasks]
    summaries = db.query(TaskReportSummary).filter(TaskReportSummary.task_id.in_(task_ids)).all() if task_ids else []
    report_status_by_task = {row.task_id: row.report_status for row in summaries}
    return build_batch_report_zip(batch_id, tasks, servers_by_id, report_status_by_task)
