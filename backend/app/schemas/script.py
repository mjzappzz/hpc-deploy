from datetime import datetime
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScriptBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)
    version: str | None = Field(default=None, max_length=50)
    file_path: str = Field(min_length=1, max_length=255)
    description: str | None = None
    enabled: bool = True
    dangerous: bool = False
    params_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params_schema", mode="before")
    @classmethod
    def parse_params_schema(cls, value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"params_schema is not valid JSON: {exc.msg}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("params_schema must be a JSON object")
            return parsed
        raise ValueError("params_schema must be a JSON object")


class ScriptCreate(ScriptBase):
    pass


class ScriptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    version: str | None = Field(default=None, max_length=50)
    file_path: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    enabled: bool | None = None
    dangerous: bool | None = None
    params_schema: dict[str, Any] | None = None

    @field_validator("params_schema", mode="before")
    @classmethod
    def parse_params_schema(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if value == "":
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"params_schema is not valid JSON: {exc.msg}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("params_schema must be a JSON object")
            return parsed
        raise ValueError("params_schema must be a JSON object")


class ScriptRead(ScriptBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
