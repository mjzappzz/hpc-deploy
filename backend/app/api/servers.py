from datetime import datetime
from pathlib import Path
from time import monotonic
import concurrent.futures
import logging

from app.core.audit import write_audit_log
from app.core.config import BACKEND_ROOT
from app.core.ssh_detector import DEFAULT_DETECT_TIMEOUT, ServerDetectError, detect_server_info, summarize_detect_result
from app.models.settings import SystemSetting
from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.core.ssh_tester import SSHTestError, test_ssh_connection
from app.db.database import SessionLocal, get_db
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
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["servers"])
KEYS_DIR = (BACKEND_ROOT / "keys").resolve()


def _get_probe_timeout(db: Session) -> int:
    """Read probe_timeout_seconds from system settings, falling back to DEFAULT_DETECT_TIMEOUT."""
    setting = db.get(SystemSetting, "probe_timeout_seconds")
    if setting is None:
        return DEFAULT_DETECT_TIMEOUT
    try:
        return int(setting.value)
    except (ValueError, TypeError):
        return DEFAULT_DETECT_TIMEOUT


def _get_server_or_404(db: Session, server_id: int) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")
    return server


def _server_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        return {"key_path": None, "password": server.password}
    return {"key_path": server.key_path, "password": None}


def _build_probe_response(server: Server, *, success: bool, error: str | None = None, timings: dict[str, float] | None = None) -> ServerDetectResponse:
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
        timings=timings,
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
    write_audit_log(
        db, action="server.create", target_type="server", status="success",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"created server {server.name} ({server.host})",
        detail={"host": server.host, "port": server.port, "username": server.username, "auth_type": server.auth_type},
    )
    return server


PROBE_ALL_MAX_WORKERS = 8


@router.post("/probe-all", response_model=ProbeAllResponse)
def probe_all_servers(
    db: Session = Depends(get_db),
    include_offline: bool = Query(False, description="if false, skip known-offline servers"),
) -> ProbeAllResponse:
    all_servers = db.query(Server).order_by(Server.id.desc()).all()
    total = len(all_servers)

    if total == 0:
        logger.info("[probe-all] no servers to probe")
        return ProbeAllResponse(total=0, probed=0, online=0, offline=0, results=[], total_elapsed_seconds=0)

    probe_all_start = monotonic()

    # Split servers into "to probe" and "skipped"
    if include_offline:
        probe_servers = list(all_servers)
        skipped_results: list[ProbeAllResult] = []
    else:
        probe_servers = [s for s in all_servers if s.status != "offline"]
        skipped_results = [
            ProbeAllResult(
                server_id=s.id,
                name=s.name,
                host=s.host,
                status=s.status or "offline",
                last_check_at=s.last_check_at,
                last_error=s.last_error,
                skipped=True,
                reason="server is offline, skipped by default (include_offline=false)",
            )
            for s in all_servers
            if s.status == "offline"
        ]

    probed_count = len(probe_servers)
    skipped_count = len(skipped_results)

    max_workers = min(PROBE_ALL_MAX_WORKERS, probed_count) if probed_count else 1

    if probed_count == 0:
        total_elapsed = round(monotonic() - probe_all_start, 3)
        logger.info(
            "[probe-all] all %d servers skipped, total_elapsed=%.3fs",
            skipped_count, total_elapsed,
        )
        return ProbeAllResponse(
            total=total,
            probed=0,
            online=0,
            offline=0,
            skipped=skipped_count,
            results=skipped_results,
            total_elapsed_seconds=total_elapsed,
        )

    probe_timeout = _get_probe_timeout(db)

    logger.info(
        "[probe-all] start probed=%d skipped=%d max_workers=%d timeout=%d include_offline=%s",
        probed_count, skipped_count, max_workers, probe_timeout, include_offline,
    )

    for s in probe_servers:
        logger.info("[probe-all] submit server_id=%d name=%s", s.id, s.name)

    def _probe_in_thread(sid: int, timeout: int) -> ProbeAllResult:
        """Probe one server in a dedicated thread with its own DB session."""
        start = monotonic()
        thread_db = SessionLocal()
        try:
            server = thread_db.get(Server, sid)
            if server is None:
                logger.info("[probe-one] server_id=%d — deleted before probe", sid)
                return ProbeAllResult(
                    server_id=sid,
                    name="(deleted)",
                    host="",
                    status="offline",
                    last_check_at=None,
                    last_error="server not found at probe time",
                    elapsed_seconds=round(monotonic() - start, 3),
                )

            logger.info("[probe-one] start server_id=%d name=%s", server.id, server.name)
            server_start = monotonic()

            try:
                raw_result, timings = detect_server_info(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    timeout=timeout,
                    **_server_auth_kwargs(server),
                )
                summary = summarize_detect_result(raw_result)
                server.status = "online"
                server.last_check_at = datetime.utcnow()
                server.last_error = None
                server.os_info = summary["os_info"]
                server.cpu_info = summary["cpu_info"]
                server.memory_info = summary["memory_info"]
                server.disk_info = summary["disk_info"]
                server.gpu_info = summary["gpu_info"]
                server.network_info = summary["network_info"]
                thread_db.commit()
                thread_db.refresh(server)
                elapsed = round(monotonic() - server_start, 3)
                logger.info(
                    "[probe-one] done server_id=%d name=%s status=online elapsed=%.3fs",
                    server.id, server.name, elapsed,
                )
                return ProbeAllResult(
                    server_id=server.id,
                    name=server.name,
                    host=server.host,
                    status="online",
                    last_check_at=server.last_check_at,
                    last_error=None,
                    elapsed_seconds=elapsed,
                    timings=timings,
                )
            except ServerDetectError as exc:
                server.status = "offline"
                server.last_error = str(exc)
                # Do NOT update last_check_at on failure
                thread_db.commit()
                thread_db.refresh(server)
                elapsed = round(monotonic() - server_start, 3)
                logger.info(
                    "[probe-one] done server_id=%d name=%s status=offline elapsed=%.3fs error=%s",
                    server.id, server.name, elapsed, str(exc),
                )
                return ProbeAllResult(
                    server_id=server.id,
                    name=server.name,
                    host=server.host,
                    status="offline",
                    last_check_at=server.last_check_at,
                    last_error=str(exc),
                    elapsed_seconds=elapsed,
                )
        except Exception as exc:
            try:
                server = thread_db.get(Server, sid)
                if server:
                    server.status = "offline"
                    server.last_error = f"Unexpected error: {exc}"
                    thread_db.commit()
            except Exception:
                pass
            elapsed = round(monotonic() - start, 3)
            logger.info(
                "[probe-one] done server_id=%d status=error elapsed=%.3fs error=%s",
                sid, elapsed, exc,
            )
            return ProbeAllResult(
                server_id=sid,
                name="(error)",
                host="",
                status="offline",
                last_check_at=None,
                last_error=f"Probe thread error: {exc}",
                elapsed_seconds=elapsed,
            )
        finally:
            thread_db.close()

    probed_ids = [s.id for s in probe_servers]
    results: list[ProbeAllResult] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {executor.submit(_probe_in_thread, sid, probe_timeout): sid for sid in probed_ids}
        for future in concurrent.futures.as_completed(fut_map):
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                sid = fut_map[future]
                results.append(
                    ProbeAllResult(
                        server_id=sid,
                        name="(error)",
                        host="",
                        status="offline",
                        last_check_at=None,
                        last_error=f"Thread execution error: {exc}",
                    )
                )

    results.extend(skipped_results)
    online = sum(1 for r in results if r.status == "online")
    offline_probed = sum(1 for r in results if r.status == "offline" and not r.skipped)
    total_elapsed = round(monotonic() - probe_all_start, 3)
    logger.info(
        "[probe-all] done total_elapsed=%.3fs online=%d offline=%d skipped=%d",
        total_elapsed, online, offline_probed, skipped_count,
    )
    _overall_status = "success" if online > 0 or offline_probed == 0 else "failed"
    write_audit_log(
        db, action="server.probe_all", target_type="server", status=_overall_status,
        message=f"probe all: {online} online, {offline_probed} offline, {skipped_count} skipped in {total_elapsed:.1f}s",
        detail={"total": total, "online": online, "offline": offline_probed, "skipped": skipped_count, "elapsed_seconds": total_elapsed},
    )
    return ProbeAllResponse(
        total=total,
        probed=probed_count,
        online=online,
        offline=offline_probed,
        skipped=skipped_count,
        results=results,
        total_elapsed_seconds=total_elapsed,
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
    old_name = server.name
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    write_audit_log(
        db, action="server.update", target_type="server", status="success",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"updated server {old_name}",
    )
    return server


@router.delete("/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    server = _get_server_or_404(db, server_id)
    _name = server.name
    _host = server.host
    db.delete(server)
    db.commit()
    write_audit_log(
        db, action="server.delete", target_type="server", status="success",
        target_id=str(server_id), target_name=_name,
        message=f"deleted server {_name} ({_host})",
    )
    return {"deleted": True}


@router.post("/{server_id}/test", response_model=SSHTestResponse)
def test_server_ssh(server_id: int, db: Session = Depends(get_db)) -> SSHTestResponse:
    server = _get_server_or_404(db, server_id)
    try:
        result = test_ssh_connection(
            host=server.host,
            port=server.port,
            username=server.username,
            timeout=_get_probe_timeout(db),
            **_server_auth_kwargs(server),
        )
        server.status = "online"
        server.last_check_at = datetime.utcnow()
        server.last_error = None
        db.commit()
        write_audit_log(
            db, action="server.test_ssh", target_type="server", status="success",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"SSH test succeeded for {server.name}",
        )
        return SSHTestResponse(
            success=True,
            status="online",
            hostname=result["hostname"],
            uname=result["uname"],
        )
    except SSHTestError as exc:
        server.status = "offline"
        server.last_error = str(exc)
        db.commit()
        write_audit_log(
            db, action="server.test_ssh", target_type="server", status="failed",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"SSH test failed for {server.name}: {exc}",
        )
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
    On success: status=online, last_check_at updated, last_error cleared.
    On failure: status=offline, last_error set, last_check_at NOT updated,
                existing os/cpu/memory/disk/gpu info preserved.
    """
    try:
        raw_result, timings = detect_server_info(
            host=server.host,
            port=server.port,
            username=server.username,
            timeout=_get_probe_timeout(db),
            **_server_auth_kwargs(server),
        )
        summary = summarize_detect_result(raw_result)
        server.status = "online"
        server.last_check_at = datetime.utcnow()
        server.last_error = None
        server.os_info = summary["os_info"]
        server.cpu_info = summary["cpu_info"]
        server.memory_info = summary["memory_info"]
        server.disk_info = summary["disk_info"]
        server.gpu_info = summary["gpu_info"]
        server.network_info = summary["network_info"]
        db.commit()
        db.refresh(server)
        write_audit_log(
            db, action="server.probe", target_type="server", status="success",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"probe succeeded for {server.name}",
        )
        return _build_probe_response(server, success=True, timings=timings)
    except ServerDetectError as exc:
        server.status = "offline"
        server.last_error = str(exc)
        db.commit()
        db.refresh(server)
        write_audit_log(
            db, action="server.probe", target_type="server", status="failed",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"probe failed for {server.name}: {exc}",
        )
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
        write_audit_log(
            db, action="server.deploy_public_key", target_type="server", status="failed",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"deploy public key failed: {exc}",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"deploy public key failed: {exc}") from exc
    finally:
        executor.close()

    server.auth_type = "key"
    server.key_path = str(private_key_file)
    server.password = None
    db.commit()
    db.refresh(server)
    write_audit_log(
        db, action="server.deploy_public_key", target_type="server", status="success",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"deployed public key for {server.name}",
    )
    return DeployPublicKeyResponse(
        success=True,
        message="public key deployed",
        auth_type=server.auth_type,
        private_key_path=server.key_path or str(private_key_file),
    )
