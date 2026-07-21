import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Tag validation helpers ──
TAG_MAX_LENGTH = 30
TAG_FORBIDDEN_CHARS = set(";&|`$()\n\r")
SERVER_TAG_OPTIONS = ("待压测", "测试机", "压测完成", "故障待处理")


def _sanitize_tag(tag: str) -> str:
    stripped = tag.strip()
    if not stripped:
        raise ValueError("tag must not be empty")
    if len(stripped) > TAG_MAX_LENGTH:
        raise ValueError(f"tag too long (max {TAG_MAX_LENGTH})")
    if any(ch in stripped for ch in TAG_FORBIDDEN_CHARS):
        raise ValueError(f"tag contains forbidden characters: {stripped}")
    return stripped


def _normalize_tags(tags_raw: list[str]) -> list[str]:
    if len(tags_raw) != 1:
        raise ValueError("exactly one server tag must be selected")
    cleaned = _sanitize_tag(tags_raw[0])
    if cleaned not in SERVER_TAG_OPTIONS:
        raise ValueError(f"unsupported server tag: {cleaned}")
    return [cleaned]


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
    gpu_status: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    network_info: str | None = None


class ServerCreate(ServerBase):
    password: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=lambda: ["待压测"])

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        try:
            return _normalize_tags(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


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
    gpu_status: str | None = None
    cpu_info: str | None = None
    memory_info: str | None = None
    disk_info: str | None = None
    network_info: str | None = None
    tags: list[str] | None = Field(default=None)

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        try:
            return _normalize_tags(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class ServerRead(ServerBase):
    id: int
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _extract_tags_from_orm(cls, data: Any) -> Any:
        # ── dict input (JSON response) ──
        if isinstance(data, dict):
            if "tags_json" in data and "tags" not in data:
                try:
                    tags_val = json.loads(data.pop("tags_json", "[]"))
                except (json.JSONDecodeError, TypeError):
                    tags_val = []
                data = {**data, "tags": tags_val if isinstance(tags_val, list) and tags_val else ["待压测"]}
            return data

        # ── SQLAlchemy ORM instance ──
        if hasattr(data, "__table__"):
            d = {}
            for c in data.__table__.columns:
                d[c.name] = getattr(data, c.name)
            try:
                tags_val = json.loads(d.pop("tags_json", "[]")) if d.get("tags_json") else []
            except (json.JSONDecodeError, TypeError):
                tags_val = []
            d["tags"] = tags_val if isinstance(tags_val, list) and tags_val else ["待压测"]
            return d

        return data


class DeployPublicKeyRequest(BaseModel):
    private_key_path: str = Field(min_length=1, max_length=255)


class DeployPublicKeyAllRequest(DeployPublicKeyRequest):
    server_ids: list[int] = Field(default_factory=list)


class CheckPublicKeyRequest(DeployPublicKeyAllRequest):
    pass


class DeployPublicKeyResponse(BaseModel):
    success: bool
    message: str
    auth_type: str
    private_key_path: str


class DeployPublicKeyAllItem(BaseModel):
    server_id: int
    server_name: str
    success: bool
    message: str


class DeployPublicKeyAllResponse(BaseModel):
    total: int
    success: int
    failed: int
    items: list[DeployPublicKeyAllItem]


class CheckPublicKeyItem(BaseModel):
    server_id: int
    server_name: str
    host: str
    success: bool
    deployed: bool
    status: str
    message: str


class CheckPublicKeyResponse(BaseModel):
    total: int
    items: list[CheckPublicKeyItem]


# ── Tag summary ──


class TagSummary(BaseModel):
    name: str
    server_count: int
    online_count: int = 0
    offline_count: int = 0


class TagSummaryResponse(BaseModel):
    items: list[TagSummary]
