from datetime import datetime
from pathlib import Path
from time import monotonic
import concurrent.futures
import json
import logging

from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.config import BACKEND_ROOT
from app.core.ssh_detector import DEFAULT_DETECT_TIMEOUT, ServerDetectError, detect_server_info, summarize_detect_result
from app.models.settings import SystemSetting
from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.core.ssh_tester import SSHTestError, test_ssh_connection
from app.db.database import SessionLocal, get_db
from app.models.server import Server
from app.schemas.server import (
    CheckPublicKeyItem,
    CheckPublicKeyRequest,
    CheckPublicKeyResponse,
    DeployPublicKeyAllItem,
    DeployPublicKeyAllRequest,
    DeployPublicKeyAllResponse,
    DeployPublicKeyRequest,
    DeployPublicKeyResponse,
    ServerCreate,
    ServerRead,
    ServerUpdate,
    SERVER_TAG_OPTIONS,
    TagSummaryResponse,
    TagSummary,
)
from app.schemas.detect import ProbeAllRequest, ProbeAllResponse, ProbeAllResult, ServerDetectResponse
from app.schemas.ssh import SSHTestAllRequest, SSHTestAllResponse, SSHTestAllResult, SSHTestResponse
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


def _resolve_server_key_path(key_path: str | None) -> str | None:
    """Resolve a server's key_path to an absolute path.

    处理 /backend/keys/xxx 前缀和相对路径，统一解析为绝对路径，
    避免 systemd 下 CWD 不同导致密钥找不到。
    """
    if not key_path:
        return None
    if key_path.startswith("/backend/keys/"):
        return str((KEYS_DIR / key_path.removeprefix("/backend/keys/")).resolve())
    return str(Path(key_path).expanduser().resolve())


def _server_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        return {"key_path": None, "password": server.password}
    return {"key_path": _resolve_server_key_path(server.key_path), "password": None}


def _server_public_key_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        if not server.password:
            raise SSHExecutorError("密码为空，无法登录")
        return {"key_path": None, "password": server.password}
    if not server.key_path:
        raise SSHExecutorError("私钥文件未配置，无法登录")
    return {"key_path": _resolve_server_key_path(server.key_path), "password": None}


def server_ready_for_public_key_deploy(server: Server) -> bool:
    """Only servers successfully probed after creation may receive a public key."""
    return server.status == "online" and server.last_check_at is not None


def _require_server_ready_for_public_key_deploy(server: Server) -> None:
    if not server_ready_for_public_key_deploy(server):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请先完成服务器首次探测并确认在线后再部署公钥",
        )


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
        gpu_status=server.gpu_status,
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
def list_servers(
    db: Session = Depends(get_db),
    tag: str | None = Query(None, max_length=30),
    keyword: str | None = Query(None, max_length=100),
    status: str | None = Query(None, max_length=20),
) -> list[Server]:
    q = db.query(Server)
    if tag:
        q = q.filter(Server.tags_json.contains(f'"{tag}"'))
    if status:
        q = q.filter(Server.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            Server.name.ilike(like)
            | Server.host.ilike(like)
        )
    return q.order_by(Server.id.desc()).all()


@router.get("/tags", response_model=TagSummaryResponse)
def list_server_tags(db: Session = Depends(get_db)) -> TagSummaryResponse:
    """Return tag summary: extract unique tags, count servers and online/offline per tag."""
    all_servers = db.query(Server.tags_json, Server.status).all()
    tag_counter: dict[str, dict[str, int]] = {
        tag: {"server_count": 0, "online_count": 0, "offline_count": 0}
        for tag in SERVER_TAG_OPTIONS
    }
    for (tj, status) in all_servers:
        if not tj:
            continue
        try:
            tags = json.loads(tj)
            if isinstance(tags, list):
                for t in tags:
                    if t not in SERVER_TAG_OPTIONS:
                        continue
                    entry = tag_counter[t]
                    entry["server_count"] += 1
                    if status == "online":
                        entry["online_count"] += 1
                    elif status == "offline":
                        entry["offline_count"] += 1
        except (json.JSONDecodeError, TypeError):
            continue
    items = [
        TagSummary(name=name, server_count=counts["server_count"], online_count=counts["online_count"], offline_count=counts["offline_count"])
        for name, counts in sorted(tag_counter.items(), key=lambda x: -x[1]["server_count"])
    ]
    return TagSummaryResponse(items=items)


@router.post("", response_model=ServerRead, status_code=status.HTTP_201_CREATED)
def create_server(
    payload: ServerCreate,
    db: Session = Depends(get_db),
) -> Server:
    data = payload.model_dump()
    tags_list = data.pop("tags", [])
    data["tags_json"] = json.dumps(tags_list, ensure_ascii=False)
    server = Server(**data)
    db.add(server)
    db.commit()
    db.refresh(server)
    write_audit_log(
        db, action="server.create", target_type="server", status="success",
        actor="visitor",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"created server {server.name} ({server.host})",
        detail={"host": server.host, "port": server.port, "username": server.username, "auth_type": server.auth_type, "tags": tags_list},
    )
    _probe_server(db, server)
    return server


PROBE_ALL_MAX_WORKERS = 8


@router.post("/probe-all", response_model=ProbeAllResponse)
def probe_all_servers(
    payload: ProbeAllRequest | None = None,
    db: Session = Depends(get_db),
    include_offline: bool = Query(False, description="if false, skip known-offline servers"),
) -> ProbeAllResponse:
    if payload and payload.server_ids:
        server_ids = list(dict.fromkeys(payload.server_ids))
        all_servers = db.query(Server).filter(Server.id.in_(server_ids)).order_by(Server.id.desc()).all()
    else:
        all_servers = db.query(Server).order_by(Server.id.desc()).all()
    total = len(all_servers)

    if total == 0:
        logger.info("[probe-all] no servers to probe")
        return ProbeAllResponse(total=0, probed=0, online=0, offline=0, results=[], total_elapsed_seconds=0)

    probe_all_start = monotonic()

    # server_ids requests always probe the explicit current list.
    if payload and payload.server_ids:
        probe_servers = list(all_servers)
        skipped_results = []
    elif include_offline:
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
                server.gpu_status = summary["gpu_status"]
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
        target_name=f"{online} online / {offline_probed} offline / {skipped_count} skipped",
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


@router.post("/test-ssh-all", response_model=SSHTestAllResponse)
@router.post("/test-all", response_model=SSHTestAllResponse)
def test_all_server_ssh(
    payload: SSHTestAllRequest,
    db: Session = Depends(get_db),
) -> SSHTestAllResponse:
    server_ids = list(dict.fromkeys(payload.server_ids))
    if not server_ids:
        return SSHTestAllResponse(total=0, tested=0, online=0, offline=0, results=[])

    existing_ids = [row[0] for row in db.query(Server.id).filter(Server.id.in_(server_ids)).all()]
    timeout = _get_probe_timeout(db)
    max_workers = min(PROBE_ALL_MAX_WORKERS, len(existing_ids)) if existing_ids else 1

    def _test_in_thread(sid: int) -> SSHTestAllResult:
        thread_db = SessionLocal()
        try:
            server = thread_db.get(Server, sid)
            if server is None:
                return SSHTestAllResult(
                    server_id=sid,
                    name="(deleted)",
                    host="",
                    success=False,
                    status="offline",
                    error="server not found at test time",
                )
            try:
                result = test_ssh_connection(
                    host=server.host,
                    port=server.port,
                    username=server.username,
                    timeout=timeout,
                    **_server_auth_kwargs(server),
                )
                server.status = "online"
                server.last_check_at = datetime.utcnow()
                server.last_error = None
                thread_db.commit()
                return SSHTestAllResult(
                    server_id=server.id,
                    name=server.name,
                    host=server.host,
                    success=True,
                    status="online",
                    hostname=result["hostname"],
                    uname=result["uname"],
                )
            except SSHTestError as exc:
                server.status = "offline"
                server.last_error = str(exc)
                thread_db.commit()
                return SSHTestAllResult(
                    server_id=server.id,
                    name=server.name,
                    host=server.host,
                    success=False,
                    status="offline",
                    error=str(exc),
                )
        finally:
            thread_db.close()

    results: list[SSHTestAllResult] = []
    if existing_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(_test_in_thread, sid): sid for sid in existing_ids}
            for future in concurrent.futures.as_completed(fut_map):
                sid = fut_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        SSHTestAllResult(
                            server_id=sid,
                            name="(error)",
                            host="",
                            success=False,
                            status="offline",
                            error=f"SSH test thread error: {exc}",
                        )
                    )

    online = sum(1 for result in results if result.success)
    offline = len(results) - online
    overall_status = "success" if online > 0 or offline == 0 else "failed"
    write_audit_log(
        db, action="server.test_ssh_all", target_type="server", status=overall_status,
        target_name=f"{online} online / {offline} offline",
        message=f"SSH test all: {online} online, {offline} offline",
        detail={"total": len(server_ids), "tested": len(results), "online": online, "offline": offline},
    )
    return SSHTestAllResponse(
        total=len(server_ids),
        tested=len(results),
        online=online,
        offline=offline,
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
    old_name = server.name
    data = payload.model_dump(exclude_unset=True)
    # Handle tags: convert list to json string for db column
    if "tags" in data:
        tags_list = data.pop("tags")
        if tags_list is not None:
            data["tags_json"] = json.dumps(tags_list, ensure_ascii=False)
        else:
            data["tags_json"] = "[]"
    for key, value in data.items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    detail = {}
    if "tags" in data or "tags_json" in data:
        detail["tags"] = json.loads(server.tags_json or "[]")
    write_audit_log(
        db, action="server.update", target_type="server", status="success",
        actor="visitor",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"updated server {old_name}",
        detail=detail if detail else None,
    )
    return server


@router.delete("/{server_id}")
def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict[str, bool]:
    server = _get_server_or_404(db, server_id)
    _name = server.name
    _host = server.host
    db.delete(server)
    db.commit()
    write_audit_log(
        db, action="server.delete", target_type="server", status="success",
        actor="admin",
        target_id=str(server_id), target_name=_name,
        server_id=server_id, server_name=_name,
        message=f"deleted server {_name} ({_host})",
        detail={"host": _host, "server_id": server_id},
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
            detail={"host": server.host, "hostname": result["hostname"], "uname": result["uname"]},
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
            detail={"host": server.host, "error": str(exc)},
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
        server.gpu_status = summary["gpu_status"]
        server.network_info = summary["network_info"]
        db.commit()
        db.refresh(server)
        write_audit_log(
            db, action="server.probe", target_type="server", status="success",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"probe succeeded for {server.name}",
            detail={"host": server.host, "os_info": server.os_info, "cpu_info": server.cpu_info,
                    "memory_info": server.memory_info, "gpu_info": server.gpu_info},
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
            detail={"host": server.host, "error": str(exc)},
        )
        return _build_probe_response(server, success=False, error=str(exc))


def _run_server_probe(server_id: int, db: Session) -> ServerDetectResponse:
    server = _get_server_or_404(db, server_id)
    return _probe_server(db, server)


def _deploy_public_key_to_server(db: Session, server: Server, private_key_file: Path, public_key: str) -> None:
    executor = SSHExecutor(timeout=10)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_public_key_auth_kwargs(server),
        )
        quoted_key = shell_quote(public_key)
        remote_command = (
            "mkdir -p \"$HOME/.ssh\" && chmod 700 \"$HOME/.ssh\" && "
            "touch \"$HOME/.ssh/authorized_keys\" && "
            f"(grep -qxF {quoted_key} \"$HOME/.ssh/authorized_keys\" || printf '%s\\n' {quoted_key} >> \"$HOME/.ssh/authorized_keys\") && "
            "chmod 600 \"$HOME/.ssh/authorized_keys\""
        )
        executor.exec_simple(remote_command)
    finally:
        executor.close()

    server.auth_type = "key"
    server.key_path = str(private_key_file)
    server.password = None
    db.commit()
    db.refresh(server)


def _check_public_key_on_server(server: Server, public_key: str) -> tuple[bool, str]:
    executor = SSHExecutor(timeout=10)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_public_key_auth_kwargs(server),
        )
        # 使用 exec_capture 避免非零退出码抛异常，使用 || true 确保退出码 0
        _exit_code, output, _error = executor.exec_capture(
            "test -f \"$HOME/.ssh/authorized_keys\" && cat \"$HOME/.ssh/authorized_keys\" || true",
            timeout_seconds=10,
        )
        lines = output.strip().splitlines()
        if public_key in lines:
            return True, "已安装当前公钥"
        return False, "未安装当前公钥"
    finally:
        executor.close()


def _load_public_key(private_key_path: str) -> tuple[Path, str]:
    private_key_file = _resolve_private_key_path(private_key_path)
    public_key_file = private_key_file.with_name(f"{private_key_file.name}.pub")
    if not public_key_file.is_file():
        public_key_display = f"backend/keys/{public_key_file.name}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"本地公钥文件不存在：{public_key_display}")

    public_key = public_key_file.read_text(encoding="utf-8").strip()
    if not public_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="public key file is empty")
    return private_key_file, public_key


@router.post("/{server_id}/deploy-public-key", response_model=DeployPublicKeyResponse)
def deploy_public_key(
    server_id: int,
    payload: DeployPublicKeyRequest,
    db: Session = Depends(get_db),
) -> DeployPublicKeyResponse:
    server = _get_server_or_404(db, server_id)
    _require_server_ready_for_public_key_deploy(server)
    private_key_file, public_key = _load_public_key(payload.private_key_path)
    try:
        _deploy_public_key_to_server(db, server, private_key_file, public_key)
    except (SSHExecutorError, OSError) as exc:
        write_audit_log(
            db, action="server.deploy_public_key", target_type="server", status="failed",
            target_id=str(server.id), target_name=server.name,
            server_id=server.id, server_name=server.name,
            message=f"deploy public key failed: {exc}",
            detail={"host": server.host, "error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"deploy public key failed: {exc}") from exc

    write_audit_log(
        db, action="server.deploy_public_key", target_type="server", status="success",
        target_id=str(server.id), target_name=server.name,
        server_id=server.id, server_name=server.name,
        message=f"deployed public key for {server.name}",
        detail={"host": server.host, "key_path": server.key_path, "auth_type": server.auth_type},
    )
    return DeployPublicKeyResponse(
        success=True,
        message="public key deployed",
        auth_type=server.auth_type,
        private_key_path=server.key_path or str(private_key_file),
    )


@router.post("/deploy-key-all", response_model=DeployPublicKeyAllResponse)
@router.post("/public-key/deploy", response_model=DeployPublicKeyAllResponse)
def deploy_public_key_all(
    payload: DeployPublicKeyAllRequest,
    db: Session = Depends(get_db),
) -> DeployPublicKeyAllResponse:
    server_ids = list(dict.fromkeys(payload.server_ids))
    private_key_file, public_key = _load_public_key(payload.private_key_path)
    if not server_ids:
        return DeployPublicKeyAllResponse(total=0, success=0, failed=0, items=[])

    existing_ids = [row[0] for row in db.query(Server.id).filter(Server.id.in_(server_ids)).all()]
    max_workers = min(PROBE_ALL_MAX_WORKERS, len(existing_ids)) if existing_ids else 1

    def _deploy_in_thread(sid: int) -> DeployPublicKeyAllItem:
        thread_db = SessionLocal()
        try:
            server = thread_db.get(Server, sid)
            if server is None:
                return DeployPublicKeyAllItem(server_id=sid, server_name="(deleted)", success=False, message="server not found")
            if not server_ready_for_public_key_deploy(server):
                return DeployPublicKeyAllItem(
                    server_id=server.id,
                    server_name=server.name,
                    success=False,
                    message="请先完成服务器首次探测并确认在线后再部署公钥",
                )
            try:
                _deploy_public_key_to_server(thread_db, server, private_key_file, public_key)
                write_audit_log(
                    thread_db, action="server.deploy_public_key", target_type="server", status="success",
                    target_id=str(server.id), target_name=server.name,
                    server_id=server.id, server_name=server.name,
                    message=f"deployed public key for {server.name}",
                    detail={"host": server.host, "key_path": server.key_path, "auth_type": server.auth_type},
                )
                return DeployPublicKeyAllItem(server_id=server.id, server_name=server.name, success=True, message="已安装当前公钥")
            except (SSHExecutorError, OSError) as exc:
                write_audit_log(
                    thread_db, action="server.deploy_public_key", target_type="server", status="failed",
                    target_id=str(server.id), target_name=server.name,
                    server_id=server.id, server_name=server.name,
                    message=f"deploy public key failed: {exc}",
                    detail={"host": server.host, "error": str(exc)},
                )
                return DeployPublicKeyAllItem(server_id=server.id, server_name=server.name, success=False, message=str(exc))
            except Exception as exc:
                return DeployPublicKeyAllItem(server_id=server.id, server_name=server.name, success=False, message=f"部署异常：{exc}")
        finally:
            thread_db.close()

    items: list[DeployPublicKeyAllItem] = []
    if existing_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(_deploy_in_thread, sid): sid for sid in existing_ids}
            for future in concurrent.futures.as_completed(fut_map):
                sid = fut_map[future]
                try:
                    items.append(future.result())
                except Exception as exc:
                    items.append(DeployPublicKeyAllItem(server_id=sid, server_name="(error)", success=False, message=str(exc)))

    missing_ids = [sid for sid in server_ids if sid not in set(existing_ids)]
    for sid in missing_ids:
        items.append(DeployPublicKeyAllItem(server_id=sid, server_name="(missing)", success=False, message="server not found"))

    success_count = sum(1 for item in items if item.success)
    failed_count = len(items) - success_count
    write_audit_log(
        db, action="server.deploy_public_key_all", target_type="server",
        status="success" if success_count > 0 or failed_count == 0 else "failed",
        target_name=f"{success_count} success / {failed_count} failed",
        message=f"deploy public key all: {success_count} success, {failed_count} failed",
        detail={"total": len(server_ids), "success": success_count, "failed": failed_count},
    )
    return DeployPublicKeyAllResponse(total=len(server_ids), success=success_count, failed=failed_count, items=items)


@router.post("/public-key/check", response_model=CheckPublicKeyResponse)
def check_public_key_all(
    payload: CheckPublicKeyRequest,
    db: Session = Depends(get_db),
) -> CheckPublicKeyResponse:
    server_ids = list(dict.fromkeys(payload.server_ids))
    _private_key_file, public_key = _load_public_key(payload.private_key_path)
    if not server_ids:
        return CheckPublicKeyResponse(total=0, items=[])

    existing_ids = [row[0] for row in db.query(Server.id).filter(Server.id.in_(server_ids)).all()]
    max_workers = min(PROBE_ALL_MAX_WORKERS, len(existing_ids)) if existing_ids else 1

    def _check_in_thread(sid: int) -> CheckPublicKeyItem:
        thread_db = SessionLocal()
        try:
            server = thread_db.get(Server, sid)
            if server is None:
                return CheckPublicKeyItem(
                    server_id=sid,
                    server_name="(deleted)",
                    host="",
                    success=False,
                    deployed=False,
                    status="CHECK_FAILED",
                    message="server not found",
                )
            try:
                deployed, message = _check_public_key_on_server(server, public_key)
                return CheckPublicKeyItem(
                    server_id=server.id,
                    server_name=server.name,
                    host=server.host,
                    success=True,
                    deployed=deployed,
                    status="INSTALLED" if deployed else "NOT_INSTALLED",
                    message=message,
                )
            except (SSHExecutorError, OSError) as exc:
                return CheckPublicKeyItem(
                    server_id=server.id,
                    server_name=server.name,
                    host=server.host,
                    success=False,
                    deployed=False,
                    status="CHECK_FAILED",
                    message=str(exc),
                )
            except Exception as exc:
                return CheckPublicKeyItem(
                    server_id=server.id,
                    server_name=server.name,
                    host=server.host,
                    success=False,
                    deployed=False,
                    status="CHECK_FAILED",
                    message=f"检测异常：{exc}",
                )
        finally:
            thread_db.close()

    items: list[CheckPublicKeyItem] = []
    if existing_ids:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(_check_in_thread, sid): sid for sid in existing_ids}
            for future in concurrent.futures.as_completed(fut_map):
                sid = fut_map[future]
                try:
                    items.append(future.result())
                except Exception as exc:
                    items.append(
                        CheckPublicKeyItem(
                            server_id=sid,
                            server_name="(error)",
                            host="",
                            success=False,
                            deployed=False,
                            status="CHECK_FAILED",
                            message=str(exc),
                        )
                    )

    for sid in [sid for sid in server_ids if sid not in set(existing_ids)]:
        items.append(
            CheckPublicKeyItem(
                server_id=sid,
                server_name="(missing)",
                host="",
                success=False,
                deployed=False,
                status="CHECK_FAILED",
                message="server not found",
            )
        )

    return CheckPublicKeyResponse(total=len(server_ids), items=items)
