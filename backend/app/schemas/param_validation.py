from typing import Any

from pydantic import BaseModel, Field


class ParamValidateRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ParamValidateResponse(BaseModel):
    success: bool
    errors: list[str] = Field(default_factory=list)

