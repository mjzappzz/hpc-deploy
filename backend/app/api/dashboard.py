from pathlib import Path

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.task_serializer import serialize_task_record
from app.db.database import get_db
from app.models.server import Server
from app.models.task import Task
from app.schemas.dashboard import (
    ArtifactStats,
    ArtifactTreeResponse,
    ArtifactTreeNode,
    DashboardSummary,
    RecentTaskItem,
    ServerStats,
    TaskStats,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    # --- server stats ---
    servers = db.query(Server).all()
    total_servers = len(servers)
    online_servers = sum(1 for s in servers if (s.status or "").lower() == "online")

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

    # --- recent tasks (last 10) ---
    recent_tasks_db = (
        db.query(Task).order_by(Task.id.desc()).limit(10).all()
    )
    recent_tasks = []
    for t in recent_tasks_db:
        record = serialize_task_record(t, db)
        recent_tasks.append(RecentTaskItem.model_validate(record))

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

    return DashboardSummary(
        servers=ServerStats(
            total=total_servers,
            online=online_servers,
            offline=total_servers - online_servers,
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
        artifacts=ArtifactStats(
            local_artifacts_count=artifacts_count,
            local_artifacts_size_bytes=artifacts_size,
        ),
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
