from app.core.ssh_detector import ServerDetectError, detect_server_info, summarize_detect_result
from app.core.ssh_tester import SSHTestError, test_ssh_connection
from app.db.database import get_db
from app.models.server import Server
from app.schemas.server import ServerCreate, ServerRead, ServerUpdate
from app.schemas.detect import ServerDetectResponse
from app.schemas.ssh import SSHTestResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/servers", tags=["servers"])


def _get_server_or_404(db: Session, server_id: int) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")
    return server


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
            key_path=server.key_path,
        )
        server.status = "online"
        db.commit()
        return SSHTestResponse(
            success=True,
            status="online",
            hostname=result["hostname"],
            uname=result["uname"],
        )
    except SSHTestError as exc:
        server.status = "offline"
        db.commit()
        return SSHTestResponse(success=False, status="offline", error=str(exc))


@router.post("/{server_id}/detect", response_model=ServerDetectResponse)
def detect_server(server_id: int, db: Session = Depends(get_db)) -> ServerDetectResponse:
    server = _get_server_or_404(db, server_id)
    try:
        raw_result = detect_server_info(
            host=server.host,
            port=server.port,
            username=server.username,
            key_path=server.key_path,
        )
        summary = summarize_detect_result(raw_result)
        server.status = "online"
        server.os_info = summary["os_info"]
        server.cpu_info = summary["cpu_info"]
        server.memory_info = summary["memory_info"]
        server.disk_info = summary["disk_info"]
        server.gpu_info = summary["gpu_info"]
        server.network_info = summary["network_info"]
        db.commit()
        return ServerDetectResponse(success=True, status="online", **summary)
    except ServerDetectError as exc:
        server.status = "offline"
        db.commit()
        return ServerDetectResponse(success=False, status="offline", error=str(exc))
