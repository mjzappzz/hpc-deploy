from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServerBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    auth_type: str = Field(default="key", max_length=20)
    key_path: str | None = Field(default=None, max_length=255)
    status: str = Field(default="unknown", max_length=20)
    last_check_at: datetime | None = None
    last_error: str | None = None
    os_info: str | None = None
    gpu_info: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    network_info: str | None = None


class ServerCreate(ServerBase):
    password: str | None = Field(default=None, max_length=255)


class ServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=100)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, min_length=1, max_length=100)
    auth_type: str | None = Field(default=None, max_length=20)
    key_path: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=20)
    last_check_at: datetime | None = None
    last_error: str | None = None
    os_info: str | None = None
    gpu_info: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    network_info: str | None = None


class ServerRead(ServerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeployPublicKeyRequest(BaseModel):
    private_key_path: str = Field(min_length=1, max_length=255)


class DeployPublicKeyResponse(BaseModel):
    success: bool
    message: str
    auth_type: str
    private_key_path: str
