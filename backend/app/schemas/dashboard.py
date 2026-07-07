from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ServerStats(BaseModel):
    total: int = 0
    online: int = 0
    offline: int = 0


class TaskStats(BaseModel):
    total: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    canceled: int = 0
    pending: int = 0
    canceling: int = 0


class RecentTaskItem(BaseModel):
    task_id: str
    server_name: str | None = None
    server_host: str | None = None
    task_type: str | None = None
    file_name: str | None = None
    file_path: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    command_preview: str | None = None
    params: dict[str, Any] | None = None
    duration_seconds: int | None = None
    final_status: str | None = None


class ArtifactStats(BaseModel):
    local_artifacts_count: int = 0
    local_artifacts_size_bytes: int = 0


class ArtifactTreeNode(BaseModel):
    name: str
    relative_path: str
    type: str = "directory"
    size_bytes: int = 0
    children: list["ArtifactTreeNode"] = []


class ArtifactTreeResponse(BaseModel):
    root: str = "backend/data/artifacts"
    total_size_bytes: int = 0
    total_dirs: int = 0
    truncated: bool = False
    warnings: list[str] = []
    items: list[ArtifactTreeNode] = []


class DashboardSummary(BaseModel):
    servers: ServerStats = ServerStats()
    tasks: TaskStats = TaskStats()
    recent_tasks: list[RecentTaskItem] = []
    artifacts: ArtifactStats = ArtifactStats()
