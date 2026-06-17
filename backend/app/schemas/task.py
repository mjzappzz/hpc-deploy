from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TaskRead(BaseModel):
    id: int
    task_id: str
    server_id: int
    script_id: int
    status: str
    params: dict[str, Any] | None
    start_time: datetime | None
    end_time: datetime | None
    exit_code: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

