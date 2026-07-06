from pydantic import BaseModel


class SSHTestAllRequest(BaseModel):
    server_ids: list[int]


class SSHTestResponse(BaseModel):
    success: bool
    status: str
    hostname: str | None = None
    uname: str | None = None
    error: str | None = None


class SSHTestAllResult(BaseModel):
    server_id: int
    name: str
    host: str
    success: bool
    status: str
    hostname: str | None = None
    uname: str | None = None
    error: str | None = None


class SSHTestAllResponse(BaseModel):
    total: int
    tested: int
    online: int
    offline: int
    results: list[SSHTestAllResult]
