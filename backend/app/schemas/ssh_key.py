from pydantic import BaseModel


class SSHKeyItem(BaseModel):
    key_name: str
    private_key_name: str
    public_key_name: str | None = None
    private_key_path: str
    has_public_key: bool = False
    display_name: str


class SSHKeyListResponse(BaseModel):
    items: list[SSHKeyItem] = []
