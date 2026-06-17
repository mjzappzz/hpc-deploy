from datetime import datetime

from pydantic import BaseModel


class ScriptFileRead(BaseModel):
    name: str
    path: str
    relative_path: str
    physical_category: str
    display_category: str
    size: int
    updated_at: datetime
    executable: bool
    is_text: bool
    previewable: bool


class ScriptFilePreviewRead(ScriptFileRead):
    content: str | None
    truncated: bool
    message: str | None
