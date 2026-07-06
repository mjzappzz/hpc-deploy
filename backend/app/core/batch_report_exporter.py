import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.artifact_collector import ARTIFACTS_DIR
from app.models.server import Server
from app.models.task import Task
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


def _build_server_report_zip(
    server_name: str,
    timestamp: str,
    batch_id: str,
    tasks: list[Task],
) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix=f"hpcdeploy-server-{batch_id}-", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    root_folder = f"{_safe_zip_name(server_name)}_压测报告"
    used_names: set[str] = set()
    missing_lines: list[str] = []
    summary: dict[str, object] = {
        "batch_id": batch_id,
        "server_name": server_name,
        "generated_at": datetime.now().isoformat(),
        "task_count": len(tasks),
        "tasks": [],
    }

    with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for task in tasks:
            reports = _iter_report_files(task.task_id)
            task_summary = {
                "task_id": task.task_id,
                "file_name": task.file_name,
                "status": task.status,
                "reports": [],
                "missing": not reports,
            }
            if not reports:
                missing_lines.append(f"{task.task_id} {task.file_name or '-'}: xlsx report missing")

            for index, report in enumerate(reports, start=1):
                candidate = f"{root_folder}/{report.name}"
                while candidate in used_names:
                    candidate = f"{root_folder}/{report.stem}_{index}_{len(used_names)}{report.suffix}"
                used_names.add(candidate)
                zf.write(report, candidate)
                task_summary["reports"].append(candidate)

            summary["tasks"].append(task_summary)

        zf.writestr(
            f"{root_folder}/summary.json",
            json.dumps(summary, ensure_ascii=False, indent=2),
        )
        if missing_lines:
            zf.writestr(f"{root_folder}/missing.txt", "\n".join(missing_lines) + "\n")

    return tmp_path


def build_batch_report_zip(batch_id: str, tasks: list[Task], servers_by_id: dict[int, Server]) -> BatchReportZip:
    if not tasks:
        raise ValueError("batch has no tasks")

    created_at = tasks[0].created_at or datetime.now()
    timestamp = created_at.strftime("%Y%m%d_%H%M%S")
    fallback_server_name = f"{batch_id}_server"
    zip_filename = f"{_safe_zip_name(batch_id)}_压测报告_{timestamp}.zip"

    tmp = tempfile.NamedTemporaryFile(prefix=f"hpcdeploy-{batch_id}-", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        server_name = _server_name_for_task(task, servers_by_id, fallback_server_name)
        grouped.setdefault(server_name, []).append(task)

    with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for server_name, server_tasks in sorted(grouped.items(), key=lambda item: item[0]):
            server_zip = _build_server_report_zip(server_name, timestamp, batch_id, server_tasks)
            try:
                arcname = f"{_safe_zip_name(server_name)}_压测报告_{timestamp}.zip"
                zf.write(server_zip, arcname)
            finally:
                server_zip.unlink(missing_ok=True)

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
    return build_batch_report_zip(batch_id, tasks, servers_by_id)
