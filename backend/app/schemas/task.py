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


class GpuDriverRunRequest(BaseModel):
    """Rocky 9.4 NVIDIA .run installation request."""

    server_id: int = Field(ge=1)
    driver_type: Literal["geforce", "datacenter"]
    driver_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    driver_upload_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    force_install_if_driver_exists: bool = False


class GpuDriverUploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int
    driver_type: Literal["geforce", "datacenter"]


class GpuDriverBatchRunRequest(BaseModel):
    server_ids: list[int] = Field(min_length=2)
    driver_type: Literal["geforce", "datacenter"]
    driver_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    driver_upload_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    force_install_if_driver_exists: bool = False


class CudaToolkitRunRequest(BaseModel):
    server_id: int = Field(ge=1)
    cuda_version: Literal["11.8", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.8", "12.9", "13.0"] = "12.8"
    force_install: bool = False


class CudaToolkitBatchRunRequest(BaseModel):
    server_ids: list[int] = Field(min_length=2)
    cuda_version: Literal["11.8", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.8", "12.9", "13.0"] = "12.8"
    force_install: bool = False


class ManagedSuiteCreateRequest(BaseModel):
    suite_type: Literal["base_system", "gpu_software"]
    server_ids: list[int] = Field(min_length=1)
    actions: list[Literal["disable_lock_sleep", "lock_release", "gpu_driver", "cuda_toolkit"]] = Field(min_length=2, max_length=2)
    driver_type: Literal["geforce", "datacenter"] | None = None
    driver_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    driver_upload_id: str | None = Field(default=None, min_length=24, max_length=24, pattern="^[a-f0-9]{24}$")
    force_install_if_driver_exists: bool = False
    cuda_version: Literal["11.8", "12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.8", "12.9", "13.0"] = "12.8"
    force_install_cuda: bool = False


class GpuDriverLibraryItem(BaseModel):
    driver_id: str
    driver_type: Literal["geforce", "datacenter"]
    label: str
    filename: str
    size: int
    uploaded_at: datetime


class TaskRetryResponse(BaseModel):
    original_task_id: str
    retry_task_id: str
    status: str


class BatchTaskRetryResponse(BaseModel):
    original_task_id: str
    retry_task_id: str
    batch_id: str
    server_id: int
    sequence_index: int
    depends_on_task_id: str | None = None
    status: str


class TaskCancelRequest(BaseModel):
    delete_remote_files: bool = False


class TaskCancelResponse(BaseModel):
    task_id: str
    status: str
    message: str | None = None


class BatchCancelRequest(BaseModel):
    delete_remote: bool = False


class BatchCancelItem(BaseModel):
    task_id: str
    old_status: str
    new_status: str
    message: str


class BatchCancelResponse(BaseModel):
    batch_id: str
    total: int
    canceled: int
    skipped: int
    failed: int
    items: list[BatchCancelItem]


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
    server_username: str | None = None
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
    final_status: str | None = None
    report_status: str | None = None
    failure_reason: str | None = None
    outcome_message: str | None = None

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


class TaskLocalArtifactsCleanupResponse(BaseModel):
    task_id: str
    local_artifacts_removed: bool
    task_history_deleted: bool
    messages: list[str]


class BatchLocalArtifactsCleanupResponse(BaseModel):
    batch_id: str
    deleted_tasks: int
    local_artifacts_removed: int
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
    stress_duration_seconds: int | None = None  # configured test duration (from task params)


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
    username: str | None = None
    status: str  # execution status
    final_status: str = "UNKNOWN"  # unified status (considers report)
    report_status: str = "UNKNOWN"
    sequence_index: int | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    remote_work_dir: str | None = None
    command_preview: str | None = None
    has_artifacts: bool = False
    error_summary: str | None = None
    failure_reason: str | None = None
    params: dict[str, Any] | None = None  # task params (stress duration, etc.)


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
    fan_speed: str | None = None
    power_draw: str | None = None
    power_limit: str | None = None
    performance_state: str | None = None
    bus_id: str | None = None


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
    attribution: str = ""
    title: str
    conclusion: str = ""
    summary: str
    possible_causes: list[str]
    suggestions: list[str]
    risk_tips: list[str] = []
    matched_patterns: list[str]
    evidence: list[str]


class TaskDiagnosisResponse(BaseModel):
    task_id: str
    task_name: str
    status: str  # execution status (legacy, kept for backward compat)
    execution_status: str
    report_status: str
    final_status: str
    diagnosis: TaskDiagnosisItem
