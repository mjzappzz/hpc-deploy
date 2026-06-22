from app.core.config import BACKEND_ROOT
from app.schemas.ssh_key import SSHKeyItem, SSHKeyListResponse
from fastapi import APIRouter

router = APIRouter(prefix="/ssh-keys", tags=["ssh-keys"])

KEYS_DIR = BACKEND_ROOT / "keys"


@router.get("", response_model=SSHKeyListResponse)
def list_ssh_keys() -> SSHKeyListResponse:
    items: list[SSHKeyItem] = []

    if not KEYS_DIR.is_dir():
        return SSHKeyListResponse(items=items)

    for entry in sorted(KEYS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith("."):
            continue
        if entry.suffix == ".pub":
            continue
        if not entry.is_file():
            continue
        public_key_file = entry.with_name(f"{entry.name}.pub")
        items.append(
            SSHKeyItem(
                key_name=entry.name,
                private_key_name=entry.name,
                public_key_name=public_key_file.name if public_key_file.is_file() else None,
                private_key_path=str(entry.resolve()),
                has_public_key=public_key_file.is_file(),
                display_name=f"{entry.name} / {public_key_file.name}" if public_key_file.is_file() else entry.name,
            )
        )

    return SSHKeyListResponse(items=items)
