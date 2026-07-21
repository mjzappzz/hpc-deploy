from datetime import datetime

from pydantic import BaseModel


class ScriptFileRead(BaseModel):
    name: str
    path: str
    resolved_path: str | None = None
    relative_path: str
    physical_category: str
    display_category: str
    size: int
    updated_at: datetime | None = None
    executable: bool
    is_text: bool
    previewable: bool
    content_version: str | None = None
    filename_version: str | None = None
    version_consistent: bool | None = None
    sha256: str | None = None
    encoding: str | None = None


class ScriptFilePreviewRead(ScriptFileRead):
    content: str | None
    truncated: bool
    message: str | None
