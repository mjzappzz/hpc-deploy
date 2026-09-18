from datetime import datetime, timedelta
from pathlib import Path
import shutil

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.task_serializer import serialize_task_record
from app.db.database import get_db, sqlite_path
from app.models.settings import SystemSetting
from app.models.server import Server, is_server_archived
from app.models.task import Task
from app.schemas.dashboard import (
    ArtifactStats,
    ArtifactTreeResponse,
    ArtifactTreeNode,
    DashboardSummary,
    RecentCompletedBatchItem,
    RecentTaskItem,
    ServerStats,
    StorageStats,
    TaskStats,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTIVE_TASK_STATUSES = (
    "PENDING", "CONNECTING", "PREPARING", "UPLOADING",
    "WAITING_REBOOT", "RUNNING", "CANCELING",
)
COMPLETED_TASK_STATUSES = ("SUCCESS", "FAILED")
BATCH_TERMINAL_TASK_STATUSES = ("SUCCESS", "FAILED", "CANCELED")
ONLINE_STATUS_MAX_AGE = timedelta(hours=1)


def _count_server_statuses(
    servers: list[Server],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    checked_at = now or datetime.utcnow()
    managed_servers = [server for server in servers if not is_server_archived(server)]
    counts = {"total": len(managed_servers), "online": 0, "offline": 0, "unknown": 0}
    for server in managed_servers:
        status = (server.status or "unknown").lower()
        if status == "online" and (
            not server.last_check_at
            or checked_at - server.last_check_at > ONLINE_STATUS_MAX_AGE
        ):
            status = "unknown"
        if status not in {"online", "offline"}:
            status = "offline"
        counts[status] += 1
    return counts


def _count_archived_servers(servers: list[Server]) -> int:
    return sum(1 for server in servers if is_server_archived(server))


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    # --- server stats ---
    servers = db.query(Server).all()
    server_statuses = _count_server_statuses(servers)

    # --- task stats ---
    tasks_count = db.query(Task).count()
    running_count = db.query(Task).filter(Task.status == "RUNNING").count()
    success_count = db.query(Task).filter(Task.status == "SUCCESS").count()
    failed_count = db.query(Task).filter(Task.status == "FAILED").count()
    canceled_count = db.query(Task).filter(Task.status == "CANCELED").count()
    canceling_count = db.query(Task).filter(Task.status == "CANCELING").count()
    pending_count = db.query(Task).filter(
        Task.status.in_(["PENDING", "CONNECTING", "PREPARING", "UPLOADING"])
    ).count()

    # --- active tasks (unlimited; dashboard is an operations view) ---
    recent_tasks_db = (
        db.query(Task)
        .filter(Task.status.in_(ACTIVE_TASK_STATUSES))
        .order_by(Task.id.desc())
        .all()
    )
    recent_tasks = []
    for t in recent_tasks_db:
        record = serialize_task_record(t, db)
        recent_tasks.append(RecentTaskItem.model_validate(record))

    # --- recently completed tasks (latest fifty successful or failed tasks) ---
    recent_completed_tasks_db = (
        db.query(Task)
        .filter(Task.status.in_(COMPLETED_TASK_STATUSES))
        .order_by(Task.end_time.desc().nullslast(), Task.id.desc())
        .limit(50)
        .all()
    )
    recent_completed_tasks = []
    for t in recent_completed_tasks_db:
        record = serialize_task_record(t, db)
        recent_completed_tasks.append(RecentTaskItem.model_validate(record))

    # Select recent batches first, then load all children for each selected
    # batch. This keeps the aggregate complete even when a batch has many
    # servers/tasks, and reuses Task History's final-status semantics.
    recent_batch_rows = (
        db.query(Task.batch_id, func.max(Task.end_time).label("end_time"), func.max(Task.id).label("last_id"))
        .filter(Task.batch_id.isnot(None), Task.hidden_from_history == 0)
        .filter(Task.status.in_(BATCH_TERMINAL_TASK_STATUSES))
        .group_by(Task.batch_id)
        .order_by(func.max(Task.end_time).desc().nullslast(), func.max(Task.id).desc())
        .limit(50)
        .all()
    )
    recent_completed_batches = []
    if recent_batch_rows:
        from app.api.tasks import _compute_batch_status, _latest_batch_attempts

        batch_ids = [row.batch_id for row in recent_batch_rows]
        child_tasks = db.query(Task).filter(
            Task.batch_id.in_(batch_ids), Task.hidden_from_history == 0,
        ).all()
        tasks_by_batch: dict[str, list[Task]] = {}
        for task in child_tasks:
            if task.batch_id:
                tasks_by_batch.setdefault(task.batch_id, []).append(task)

        for row in recent_batch_rows:
            tasks = tasks_by_batch.get(row.batch_id, [])
            status = _compute_batch_status(tasks, db)
            if status not in {"SUCCESS", "FAILED", "PARTIAL_FAILED", "CANCELED", "PARTIAL_CANCELED"}:
                continue
            effective_tasks = _latest_batch_attempts(tasks)
            success = failed = canceled = 0
            servers: list[str] = []
            for task in effective_tasks:
                record = serialize_task_record(task, db)
                final_status = str(record.get("final_status") or "UNKNOWN").upper()
                if final_status == "SUCCESS":
                    success += 1
                elif final_status == "FAILED":
                    failed += 1
                elif task.status == "CANCELED":
                    canceled += 1
                server = str(record.get("server_name") or record.get("server_host") or f"Server #{task.server_id}")
                if server not in servers:
                    servers.append(server)
            created_at = min((task.created_at for task in tasks if task.created_at), default=None)
            end_time = max((task.end_time for task in tasks if task.end_time), default=None)
            start_time = min((task.start_time for task in effective_tasks if task.start_time), default=None)
            duration_seconds = int((end_time - start_time).total_seconds()) if end_time and start_time else None
            recent_completed_batches.append(RecentCompletedBatchItem(
                batch_id=row.batch_id,
                task_type=tasks[0].task_type if tasks else None,
                file_name=next((task.file_name for task in effective_tasks if task.file_name), None),
                file_path=next((task.file_path for task in effective_tasks if task.file_path), None),
                params=next((task.params for task in effective_tasks if task.params), None),
                total=len(effective_tasks),
                success=success,
                failed=failed,
                canceled=canceled,
                status=status,
                server_count=len(servers),
                servers=servers,
                created_at=created_at,
                end_time=end_time or row.end_time,
                duration_seconds=duration_seconds,
            ))

    # --- local artifact stats ---
    artifacts_count = 0
    artifacts_size = 0
    try:
        if ARTIFACTS_DIR.is_dir():
            for entry in ARTIFACTS_DIR.iterdir():
                if entry.is_dir():
                    artifacts_count += 1
                    for f in entry.rglob("*"):
                        if f.is_file():
                            try:
                                artifacts_size += f.stat().st_size
                            except OSError:
                                pass
    except OSError:
        pass

    storage = StorageStats()
    try:
        usage = shutil.disk_usage(ARTIFACTS_DIR)
        db_bytes = sqlite_path.stat().st_size if sqlite_path and sqlite_path.exists() else 0
        cleanup = db.query(SystemSetting).filter(SystemSetting.key == "auto_cleanup_last_status").first()
        warning_bytes = 10 * 1024**3
        block_bytes = 5 * 1024**3
        capacity_status = "pass" if usage.free >= warning_bytes else "warning" if usage.free >= block_bytes else "blocked"
        storage = StorageStats(total_bytes=usage.total, free_bytes=usage.free, used_bytes=usage.used,
                               artifacts_bytes=artifacts_size, database_bytes=db_bytes,
                               cleanup_status=cleanup.value if cleanup else "unknown",
                               capacity_status=capacity_status,
                               usage_percent=usage.used / usage.total * 100 if usage.total else None)
    except OSError:
        pass

    return DashboardSummary(
        servers=ServerStats(
            **server_statuses,
            archived=_count_archived_servers(servers),
        ),
        tasks=TaskStats(
            total=tasks_count,
            running=running_count,
            success=success_count,
            failed=failed_count,
            canceled=canceled_count,
            pending=pending_count,
            canceling=canceling_count,
        ),
        recent_tasks=recent_tasks,
        recent_completed_tasks=recent_completed_tasks,
        recent_completed_batches=recent_completed_batches,
        artifacts=ArtifactStats(
            local_artifacts_count=artifacts_count,
            local_artifacts_size_bytes=artifacts_size,
        ),
        storage=storage,
    )


@router.get("/artifacts/tree", response_model=ArtifactTreeResponse)
def get_artifacts_tree(
    max_depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=200, ge=1, le=500),
) -> ArtifactTreeResponse:
    warnings: list[str] = []
    items: list[ArtifactTreeNode] = []
    total_size = 0
    total_dirs = 0
    truncated = False

    if not ARTIFACTS_DIR.is_dir():
        return ArtifactTreeResponse(
            items=items,
            warnings=["artifacts directory not found"],
        )

    try:
        task_dirs = sorted(
            [d for d in ARTIFACTS_DIR.iterdir() if d.is_dir()],
            key=lambda d: _dir_size(d),
            reverse=True,
        )
    except OSError as exc:
        return ArtifactTreeResponse(
            warnings=[f"failed to list artifacts directory: {exc}"],
        )

    if len(task_dirs) > limit:
        truncated = True
        warnings.append(f"目录数量过多，仅显示前 {limit} 个目录")
        task_dirs = task_dirs[:limit]

    for d in task_dirs:
        try:
            node = _build_artifact_tree_item(d, ARTIFACTS_DIR, max_depth, current_depth=1)
            if node is not None:
                items.append(node)
                total_size += node.size_bytes
                total_dirs += _count_dirs(node)
        except OSError as exc:
            warnings.append(f"skip directory {d.name}: {exc}")

    return ArtifactTreeResponse(
        root="backend/data/artifacts",
        total_size_bytes=total_size,
        total_dirs=total_dirs,
        truncated=truncated,
        warnings=warnings,
        items=items,
    )


def _dir_size(path: Path) -> int:
    """Return total size of all files under *path*."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _count_dirs(node: ArtifactTreeNode) -> int:
    """Count directory nodes in a tree (including root)."""
    count = 1
    for child in node.children:
        count += _count_dirs(child)
    return count


def _build_artifact_tree_item(
    path: Path,
    base_path: Path,
    max_depth: int,
    current_depth: int = 1,
) -> ArtifactTreeNode | None:
    """Recursively build an ArtifactTreeNode for *path* relative to *base_path*.

    Only directories are returned as nodes (no leaf files).
    If *current_depth* exceeds *max_depth*, children are not scanned.
    """
    try:
        if not path.is_dir():
            return None
    except OSError:
        return None

    rel = path.relative_to(base_path).as_posix()

    size = _dir_size(path)
    children: list[ArtifactTreeNode] = []

    if current_depth < max_depth:
        try:
            sub_dirs = sorted(
                [p for p in path.iterdir() if p.is_dir()],
                key=lambda d: _dir_size(d),
                reverse=True,
            )
        except OSError:
            sub_dirs = []

        for sub in sub_dirs:
            child = _build_artifact_tree_item(sub, base_path, max_depth, current_depth + 1)
            if child is not None:
                children.append(child)

    return ArtifactTreeNode(
        name=path.name,
        relative_path=rel,
        type="directory",
        size_bytes=size,
        children=children,
    )
