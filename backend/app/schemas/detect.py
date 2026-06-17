from pydantic import BaseModel


class ServerDetectResponse(BaseModel):
    success: bool
    status: str
    os_info: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    gpu_info: str | None = None
    network_info: str | None = None
    error: str | None = None
