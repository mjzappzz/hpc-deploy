from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ServerStats(BaseModel):
    total: int = 0
    online: int = 0
    offline: int = 0
    unknown: int = 0
    archived: int = 0


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
    batch_id: str | None = None
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
    sequence_index: int | None = None
    params: dict[str, Any] | None = None
    duration_seconds: int | None = None
    final_status: str | None = None


class RecentCompletedBatchItem(BaseModel):
    batch_id: str
    task_type: str | None = None
    file_name: str | None = None
    file_path: str | None = None
    params: dict[str, Any] | None = None
    total: int = 0
    success: int = 0
    failed: int = 0
    canceled: int = 0
    status: str
    server_count: int = 0
    servers: list[str] = []
    created_at: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: int | None = None


class ArtifactStats(BaseModel):
    local_artifacts_count: int = 0
    local_artifacts_size_bytes: int = 0


class StoragePathStats(BaseModel):
    key: str
    label: str
    path: str
    size_bytes: int = 0
    file_count: int = 0
    status: str = "available"
    error: str | None = None


class StorageBreakdownItem(BaseModel):
    key: str
    label: str
    path: str | None = None
    size_bytes: int = 0
    file_count: int = 0
    status: str = "available"
    error: str | None = None
    percentage: float | None = None


class StorageStats(BaseModel):
    total_bytes: int = 0
    free_bytes: int = 0
    used_bytes: int = 0
    artifacts_bytes: int = 0
    database_bytes: int = 0
    cleanup_status: str = "unknown"
    capacity_status: str = "unknown"
    usage_percent: float | None = None
    project_total_bytes: int | None = None
    project_total_file_count: int | None = None
    project_status: str = "unknown"
    device: str | None = None
    mountpoint: str | None = None
    inspected_paths: list[StoragePathStats] = []
    breakdown: list[StorageBreakdownItem] = []


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
    recent_completed_tasks: list[RecentTaskItem] = []
    recent_completed_batches: list[RecentCompletedBatchItem] = []
    artifacts: ArtifactStats = ArtifactStats()
    storage: StorageStats = StorageStats()
