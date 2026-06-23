from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    created_at: datetime | None = None
    actor: str | None = ""
    action: str | None = ""
    target_type: str | None = ""
    target_id: str | None = ""
    target_name: str | None = ""
    server_name: str | None = ""
    task_id: str | None = ""
    status: str | None = ""
    message: str | None = ""
    detail_json: Any = None
    client_ip: str | None = ""

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int
