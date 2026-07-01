from datetime import datetime

from pydantic import BaseModel, Field


class LocalArtifactFile(BaseModel):
    """A single file inside a task directory."""
    name: str
    relative_path: str
    size_bytes: int = 0
    size_text: str = ""
    modified_at: datetime | None = None


class LocalArtifactDirectory(BaseModel):
    """A directory (or virtual group) under the artifacts root."""
    name: str
    relative_path: str
    type: str = "directory"
    file_count: int = 0
    size_bytes: int = 0
    size_text: str = ""
    modified_at: datetime | None = None
    task_id: str | None = None
    task_display_name: str | None = None
    files: list[LocalArtifactFile] = []


class LocalArtifactsScanResult(BaseModel):
    root: str
    total_dirs: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    items: list[LocalArtifactDirectory] = []


class LocalLogsScanResult(BaseModel):
    mode: str  # "database" or "file"
    root: str | None = None
    total_files: int = 0
    total_size_bytes: int = 0
    items: list[LocalArtifactFile] = []
    message: str | None = None


class LocalArtifactsDeleteRequest(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=100)
    recursive: bool = False


class DeleteResultItem(BaseModel):
    path: str
    success: bool
    error: str | None = None


class LocalArtifactsDeleteResponse(BaseModel):
    deleted: list[DeleteResultItem]
    failed: list[DeleteResultItem]


class RemoteScanRequest(BaseModel):
    server_id: int = Field(ge=1)


class RemoteDirInfo(BaseModel):
    label: str
    remote_path: str
    exists: bool
    size_text: str = ""
    file_count: int = 0


class RemoteTaskDirInfo(BaseModel):
    """A single task directory within the tasks root."""
    dir_name: str
    remote_path: str
    exists: bool
    size_text: str = ""
    file_count: int = 0
    task_type_label: str = ""


class RemoteScanResult(BaseModel):
    server_id: int
    remote_user: str = ""
    remote_home: str = ""
    items: list[RemoteDirInfo]
    error: str | None = None
    task_dirs: list[RemoteTaskDirInfo] = []


REMOTE_TARGETS: dict[str, str] = {
    "tasks": "$HOME/hpcdeploy/tasks",
    "downloads": "$HOME/hpcdeploy/downloads",
    "tmp": "$HOME/hpcdeploy/tmp",
}

REMOTE_ALLOWED_TARGETS: set[str] = set(REMOTE_TARGETS.keys())


class RemoteDeleteRequest(BaseModel):
    server_id: int = Field(ge=1)
    target: str = Field(min_length=1, max_length=20)


class RemoteDeleteResponse(BaseModel):
    server_id: int
    target: str
    remote_path: str
    success: bool
    message: str


class RemoteTaskDirDeleteRequest(BaseModel):
    server_id: int = Field(ge=1)
    task_dir_path: str = Field(min_length=1, max_length=500)


class RemoteTaskDirDeleteResponse(BaseModel):
    server_id: int
    task_dir_path: str
    success: bool
    message: str


class ApptainerImageItem(BaseModel):
    filename: str
    relative_path: str
    size_bytes: int
    size_text: str
    modified_at: datetime | None = None


class ApptainerImageScanResult(BaseModel):
    root: str
    total_files: int
    total_size_bytes: int
    items: list[ApptainerImageItem]


# ── Remote scan-all schemas ──

class RemoteDirectoryScan(BaseModel):
    """A single target directory in a scan-all result."""
    target: str
    label: str
    remote_path: str
    exists: bool
    size_text: str = ""
    file_count: int = 0


class RemoteServerScanResult(BaseModel):
    """Per-server result in a scan-all response."""
    server_id: int
    server_name: str
    host: str
    remote_user: str = ""
    remote_home: str = ""
    status: str  # "success" or "error"
    server_status: str = ""  # synced server status: "online" / "offline"
    message: str | None = None  # human-readable summary for failed servers
    error: str | None = None
    directories: list[RemoteDirectoryScan] = []
    task_dirs: list[RemoteTaskDirInfo] = []


class RemoteScanAllResult(BaseModel):
    """Top-level scan-all response."""
    total_servers: int
    success: int
    failed: int
    items: list[RemoteServerScanResult]
