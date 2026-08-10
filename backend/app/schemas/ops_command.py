from datetime import datetime

from app.core.ops_command_rich_text import sanitize_ops_command_rich_text
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpsCommandCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title cannot be blank")
        return normalized

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return sanitize_ops_command_rich_text(value)


class OpsCommandUpdate(OpsCommandCreate):
    pass


class OpsCommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
