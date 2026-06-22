from datetime import datetime

from pydantic import BaseModel


class ServerProbeSummary(BaseModel):
    os: str | None = None
    cpu: str | None = None
    memory: str | None = None
    disk: str | None = None
    gpu: str | None = None


class ServerDetectResponse(BaseModel):
    success: bool
    server_id: int | None = None
    name: str | None = None
    host: str | None = None
    status: str
    last_check_at: datetime | None = None
    last_error: str | None = None
    os_info: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    gpu_info: str | None = None
    network_info: str | None = None
    summary: ServerProbeSummary | None = None
    error: str | None = None
    timings: dict[str, float] | None = None  # per-stage elapsed seconds for debugging


class ProbeAllResult(BaseModel):
    server_id: int
    name: str
    host: str
    status: str
    last_check_at: datetime | None = None
    last_error: str | None = None
    elapsed_seconds: float | None = None  # per-server probe duration, for debugging
    timings: dict[str, float] | None = None  # per-stage elapsed seconds for debugging
    skipped: bool = False  # True when server was not probed (e.g. offline + include_offline=False)
    reason: str | None = None  # why the server was skipped


class ProbeAllResponse(BaseModel):
    total: int
    probed: int
    online: int
    offline: int
    skipped: int = 0
    results: list[ProbeAllResult]
    total_elapsed_seconds: float | None = None  # wall-clock duration of the bulk probe
