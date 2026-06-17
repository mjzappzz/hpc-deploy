from pydantic import BaseModel


class ScriptValidateResponse(BaseModel):
    success: bool
    enabled: bool
    dangerous: bool
    file_path: str
    resolved_path: str | None = None
    params_schema_valid: bool
    error: str | None = None

