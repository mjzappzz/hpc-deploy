from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TaskType = Literal["script", "stress", "apptainer"]
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
    batch_id: str | None = None
    sequence_index: int | None = None
    depends_on_task_id: str | None = None
    params: dict[str, Any] | None
    start_time: datetime | None
    end_time: datetime | None
    exit_code: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    duration_seconds: int | None = None

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


class BatchTaskCreateRequest(BaseModel):
    server_ids: list[int] = Field(min_length=1)
    script_type: TaskType
    script_path: str = Field(min_length=1, max_length=255)
    params: dict[str, object] = Field(default_factory=dict)


class BatchTaskCreateItem(BaseModel):
    server_id: int
    server_name: str
    task_id: str | None = None
    success: bool
    status: str
    reason: str | None = None


class BatchTaskCreateResponse(BaseModel):
    batch_id: str = ""
    script_name: str = ""
    total: int
    created: int
    skipped: int
    failed: int
    items: list[BatchTaskCreateItem]


# ── Stress Suite (Phase 29A) ──


class StressSuiteCreateRequest(BaseModel):
    server_ids: list[int] = Field(min_length=1)
    script_paths: list[str] = Field(min_length=1, max_length=3)
    params: dict[str, object] = Field(default_factory=dict)


class StressSuiteCreateItem(BaseModel):
    server_id: int
    server_name: str = ""
    task_id: str = ""
    script_path: str
    task_name: str = ""
    status: str = "PENDING"


class StressSuiteCreateResponse(BaseModel):
    batch_id: str = ""
    total: int = 0
    items: list[StressSuiteCreateItem] = []


# ── Batch summary / detail (Phase 26A) ──


class BatchSummaryItem(BaseModel):
    """One batch group in the batch summary list."""
    batch_id: str
    task_type: str | None = None
    script_names: list[str] = []
    created_at: datetime
    total: int
    success: int
    failed: int
    running: int
    pending: int
    canceled: int
    status: str  # RUNNING / SUCCESS / FAILED / PARTIAL_FAILED / CANCELED / PARTIAL_CANCELED
    servers: list[str] = []


class BatchSummaryListResponse(BaseModel):
    items: list[BatchSummaryItem]
    total: int
    page: int
    page_size: int


class BatchTaskDetailItem(BaseModel):
    """One task inside a batch detail."""
    task_id: str
    task_name: str
    server_id: int
    server_name: str
    host: str
    status: str
    sequence_index: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    exit_code: int | None = None
    has_artifacts: bool = False
    error_summary: str | None = None


class BatchDetailResponse(BaseModel):
    batch_id: str
    summary: BatchSummaryItem
    tasks: list[BatchTaskDetailItem]


# ── Structured monitor response (Phase 24B) ──


class MonitorCpuMemory(BaseModel):
    available: bool = False
    cpu_usage_percent: float | None = None
    load_avg: str | None = None
    memory_total: str | None = None
    memory_used: str | None = None
    memory_usage_percent: float | None = None
    message: str | None = None


class MonitorDiskItem(BaseModel):
    mount: str
    total: str | None = None
    used: str | None = None
    available: str | None = None
    usage_percent: float | None = None


class MonitorDisk(BaseModel):
    available: bool = False
    disk_usage: list[MonitorDiskItem] = []
    message: str | None = None


class MonitorGpuItem(BaseModel):
    index: str
    name: str
    utilization_gpu: str | None = None
    memory_used: str | None = None
    memory_total: str | None = None
    temperature: str | None = None


class MonitorGpu(BaseModel):
    available: bool = False
    items: list[MonitorGpuItem] = []
    message: str | None = None


class TaskMonitorResponseStructured(BaseModel):
    task_id: str
    status: str
    sampled_at: datetime
    cpu_memory: MonitorCpuMemory
    disk: MonitorDisk
    gpu: MonitorGpu


class TaskDiagnosisItem(BaseModel):
    level: str
    category: str
    title: str
    summary: str
    possible_causes: list[str]
    suggestions: list[str]
    matched_patterns: list[str]
    evidence: list[str]


class TaskDiagnosisResponse(BaseModel):
    task_id: str
    task_name: str
    status: str
    diagnosis: TaskDiagnosisItem
