from pydantic import BaseModel


class SSHTestResponse(BaseModel):
    success: bool
    status: str
    hostname: str | None = None
    uname: str | None = None
    error: str | None = None

