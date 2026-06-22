from datetime import datetime
from pathlib import Path

from app.core.config import BACKEND_ROOT
from app.core.ssh_detector import ServerDetectError, detect_server_info, summarize_detect_result
from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.core.ssh_tester import SSHTestError, test_ssh_connection
from app.db.database import get_db
from app.models.server import Server
from app.schemas.server import (
    DeployPublicKeyRequest,
    DeployPublicKeyResponse,
    ServerCreate,
    ServerRead,
    ServerUpdate,
)
from app.schemas.detect import ProbeAllResponse, ProbeAllResult, ServerDetectResponse
from app.schemas.ssh import SSHTestResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/servers", tags=["servers"])
KEYS_DIR = (BACKEND_ROOT / "keys").resolve()


def _get_server_or_404(db: Session, server_id: int) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")
    return server


def _server_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        return {"key_path": None, "password": server.password}
    return {"key_path": server.key_path, "password": None}


def _build_probe_response(server: Server, *, success: bool, error: str | None = None) -> ServerDetectResponse:
    return ServerDetectResponse(
        success=success,
        server_id=server.id,
        name=server.name,
        host=server.host,
        status=server.status,
        last_check_at=server.last_check_at,
        last_error=server.last_error,
        os_info=server.os_info,
        cpu_info=server.cpu_info,
        memory_info=server.memory_info,
        disk_info=server.disk_info,
        gpu_info=server.gpu_info,
        network_info=server.network_info,
        summary={
            "os": server.os_info,
            "cpu": server.cpu_info,
            "memory": server.memory_info,
            "disk": server.disk_info,
            "gpu": server.gpu_info,
        },
        error=error,
    )


def _resolve_private_key_path(private_key_path: str) -> Path:
    if private_key_path.startswith("/backend/keys/"):
        candidate = (KEYS_DIR / private_key_path.removeprefix("/backend/keys/")).resolve()
    else:
        candidate = Path(private_key_path).expanduser().resolve()
    try:
        candidate.relative_to(KEYS_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="private key path must be under backend/keys")
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="private key file not found")
    if candidate.name.startswith(".") or candidate.suffix == ".pub":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid private key file")
    return candidate


@router.get("", response_model=list[ServerRead])
def list_servers(db: Session = Depends(get_db)) -> list[Server]:
    return db.query(Server).order_by(Server.id.desc()).all()


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
def create_server(payload: ServerCreate, db: Session = Depends(get_db)) -> Server:
    server = Server(**payload.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


@router.post("/probe-all", response_model=ProbeAllResponse)
def probe_all_servers(db: Session = Depends(get_db)) -> ProbeAllResponse:
    servers = db.query(Server).order_by(Server.id.desc()).all()
    results: list[ProbeAllResult] = []
    for server in servers:
        try:
            resp = _probe_server(db, server)
            results.append(
                ProbeAllResult(
                    server_id=resp.server_id or server.id,
                    name=resp.name or server.name,
                    host=resp.host or server.host,
                    status=resp.status,
                    last_check_at=resp.last_check_at,
                    last_error=resp.last_error,
                )
            )
        except Exception as exc:
            # Safety net — should not happen since _probe_server wraps exceptions,
            # but guards against unexpected errors (e.g. DB failure).
            server.status = "offline"
            server.last_error = f"Unexpected error: {exc}"
            server.last_check_at = datetime.utcnow()
            db.commit()
            db.refresh(server)
            results.append(
                ProbeAllResult(
                    server_id=server.id,
                    name=server.name,
                    host=server.host,
                    status="offline",
                    last_check_at=server.last_check_at,
                    last_error=server.last_error,
                )
            )
    online = sum(1 for r in results if r.status == "online")
    return ProbeAllResponse(
        total=len(results),
        online=online,
        offline=len(results) - online,
        results=results,
    )


@router.get("/{server_id}", response_model=ServerRead)
def get_server(server_id: int, db: Session = Depends(get_db)) -> Server:
    return _get_server_or_404(db, server_id)


@router.put("/{server_id}", response_model=ServerRead)
def update_server(
    server_id: int,
    payload: ServerUpdate,
    db: Session = Depends(get_db),
) -> Server:
    server = _get_server_or_404(db, server_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    return server


@router.delete("/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    server = _get_server_or_404(db, server_id)
    db.delete(server)
    db.commit()
    return {"deleted": True}


@router.post("/{server_id}/test", response_model=SSHTestResponse)
def test_server_ssh(server_id: int, db: Session = Depends(get_db)) -> SSHTestResponse:
    server = _get_server_or_404(db, server_id)
    try:
        result = test_ssh_connection(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        server.status = "online"
        server.last_check_at = datetime.utcnow()
        server.last_error = None
        db.commit()
        return SSHTestResponse(
            success=True,
            status="online",
            hostname=result["hostname"],
            uname=result["uname"],
        )
    except SSHTestError as exc:
        server.status = "offline"
        server.last_check_at = datetime.utcnow()
        server.last_error = str(exc)
        db.commit()
        return SSHTestResponse(success=False, status="offline", error=str(exc))


@router.post("/{server_id}/detect", response_model=ServerDetectResponse)
def detect_server(server_id: int, db: Session = Depends(get_db)) -> ServerDetectResponse:
    return _run_server_probe(server_id, db)


@router.post("/{server_id}/probe", response_model=ServerDetectResponse)
def probe_server(server_id: int, db: Session = Depends(get_db)) -> ServerDetectResponse:
    return _run_server_probe(server_id, db)


def _probe_server(db: Session, server: Server) -> ServerDetectResponse:
    """Probe a single server and update its health info in DB.
    Used by both single-server and bulk probe endpoints.
    """
    server.last_check_at = datetime.utcnow()
    try:
        raw_result = detect_server_info(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        summary = summarize_detect_result(raw_result)
        server.status = "online"
        server.last_error = None
        server.os_info = summary["os_info"]
        server.cpu_info = summary["cpu_info"]
        server.memory_info = summary["memory_info"]
        server.disk_info = summary["disk_info"]
        server.gpu_info = summary["gpu_info"]
        server.network_info = summary["network_info"]
        db.commit()
        db.refresh(server)
        return _build_probe_response(server, success=True)
    except ServerDetectError as exc:
        server.status = "offline"
        server.last_error = str(exc)
        db.commit()
        db.refresh(server)
        return _build_probe_response(server, success=False, error=str(exc))


def _run_server_probe(server_id: int, db: Session) -> ServerDetectResponse:
    server = _get_server_or_404(db, server_id)
    return _probe_server(db, server)


@router.post("/{server_id}/deploy-public-key", response_model=DeployPublicKeyResponse)
def deploy_public_key(
    server_id: int,
    payload: DeployPublicKeyRequest,
    db: Session = Depends(get_db),
) -> DeployPublicKeyResponse:
    server = _get_server_or_404(db, server_id)
    if not server.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="server password is not configured")

    private_key_file = _resolve_private_key_path(payload.private_key_path)
    public_key_file = private_key_file.with_name(f"{private_key_file.name}.pub")
    if not public_key_file.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="matching public key file not found")

    public_key = public_key_file.read_text(encoding="utf-8").strip()
    if not public_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="public key file is empty")

    executor = SSHExecutor(timeout=10)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=None,
            password=server.password,
        )
        quoted_key = shell_quote(public_key)
        remote_command = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            "touch ~/.ssh/authorized_keys && "
            f"(grep -qxF {quoted_key} ~/.ssh/authorized_keys || printf '%s\\n' {quoted_key} >> ~/.ssh/authorized_keys) && "
            "chmod 600 ~/.ssh/authorized_keys"
        )
        executor.exec_simple(remote_command)
    except (SSHExecutorError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"deploy public key failed: {exc}") from exc
    finally:
        executor.close()

    server.auth_type = "key"
    server.key_path = str(private_key_file)
    server.password = None
    db.commit()
    db.refresh(server)
    return DeployPublicKeyResponse(
        success=True,
        message="public key deployed",
        auth_type=server.auth_type,
        private_key_path=server.key_path or str(private_key_file),
    )
