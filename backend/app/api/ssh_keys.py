import subprocess

from app.core.config import BACKEND_ROOT
from app.schemas.ssh_key import SSHKeyGenerateResponse, SSHKeyItem, SSHKeyListResponse
from fastapi import APIRouter, HTTPException, status

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

@router.post("/generate-default", response_model=SSHKeyGenerateResponse)
def generate_default_ssh_key() -> SSHKeyGenerateResponse:
    """Generate default id_rsa / id_rsa.pub in backend/keys/."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key = KEYS_DIR / "id_rsa"
    public_key = KEYS_DIR / "id_rsa.pub"

    if private_key.is_file() or public_key.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="默认密钥已存在，请先确认是否需要覆盖",
        )

    if not _ssh_keygen_available():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ssh-keygen 不可用，请安装 openssh-client",
        )

    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-t", "rsa",
                "-b", "4096",
                "-f", str(private_key),
                "-N", "",
                "-C", "hpcdeploy-default",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密钥生成失败: {exc.stderr or exc.stdout or str(exc)}",
        ) from exc

    # Set permissions
    try:
        private_key.chmod(0o600)
        if public_key.is_file():
            public_key.chmod(0o644)
    except OSError:
        pass  # non-fatal

    return SSHKeyGenerateResponse(
        private_key="id_rsa",
        public_key="id_rsa.pub",
        message="默认密钥生成成功",
    )


def _ssh_keygen_available() -> bool:
    try:
        result = subprocess.run(
            ["ssh-keygen", "--help"],
            capture_output=True,
            text=True,
        )
        return result.returncode in (0, 1)
    except FileNotFoundError:
        return False
