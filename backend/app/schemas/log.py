from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskLogRead(BaseModel):
    id: int
    task_id: str
    level: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

