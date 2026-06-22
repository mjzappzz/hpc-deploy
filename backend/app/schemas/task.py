from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TaskType = Literal["mpi", "stress", "test", "apptainer"]
MonitorType = Literal["top", "iostat", "nvidia-smi", "free", "df", "ps", "cpu_mem", "disk", "gpu"]


class TaskRunRequest(BaseModel):
    server_id: int = Field(ge=1)
    task_type: TaskType
    file_path: str = Field(min_length=1, max_length=255)
    duration_seconds: int | None = Field(default=None, ge=1)
    params: dict[str, object] | None = Field(default=None)


class TaskRunResponse(BaseModel):
    task_id: str
    status: str


class TaskCancelResponse(BaseModel):
    task_id: str
    status: str


class TaskMonitorRequest(BaseModel):
    type: MonitorType


class TaskMonitorResponse(BaseModel):
    success: bool
    type: MonitorType
    output: str | None = None
    error: str | None = None
    executed_at: datetime


class TaskRead(BaseModel):
    id: int
    task_id: str
    server_id: int
    server_name: str | None = None
    server_host: str | None = None
    script_id: int | None
    task_type: str | None
    file_path: str | None
    file_name: str | None
    display_category: str | None
    remote_work_dir: str | None
    command_preview: str | None
    status: str
    params: dict[str, Any] | None
    start_time: datetime | None
    end_time: datetime | None
    exit_code: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtifactFileDetail(BaseModel):
    name: str
    size: int
    type: str
    local_relative_path: str
    download_url: str


class ArtifactListResponse(BaseModel):
    artifact_dir: str
    files: list[ArtifactFileDetail]


class TaskCleanupResponse(BaseModel):
    task_id: str
    local_artifacts_removed: bool
    remote_work_dir_removed: bool
    messages: list[str]


class TaskDeleteResponse(BaseModel):
    task_id: str
    deleted: bool
    local_artifacts_removed: bool
    remote_work_dir_removed: bool
    logs_deleted: bool
    task_deleted: bool
    messages: list[str]


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int
