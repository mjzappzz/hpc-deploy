import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any

from app.core.artifact_collector import ARTIFACTS_DIR
from app.core.audit import write_audit_log
from app.core.config import BACKEND_ROOT
from app.core.ssh_executor import SSHExecutor, SSHExecutorError, shell_quote
from app.db.database import get_db
from app.models.server import Server
from app.schemas.cleanup import (
    REMOTE_ALLOWED_TARGETS,
    REMOTE_TARGETS,
    ApptainerImageItem,
    ApptainerImageScanResult,
    DeleteResultItem,
    LocalArtifactDirectory,
    LocalArtifactFile,
    LocalArtifactsDeleteRequest,
    LocalArtifactsDeleteResponse,
    LocalArtifactsScanResult,
    RemoteDeleteRequest,
    RemoteDeleteResponse,
    RemoteDirectoryScan,
    RemoteDirInfo,
    RemoteScanAllResult,
    RemoteScanRequest,
    RemoteScanResult,
    RemoteServerScanResult,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cleanup", tags=["cleanup"])

ARTIFACTS_ROOT = ARTIFACTS_DIR.resolve()

# ── Helpers ──


def _format_size_text(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    if bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"


def _ensure_inside_root(resolved: Path, root: Path, path_label: str) -> None:
    """Security check: ensure resolved path stays inside the allowed root."""
    try:
        resolved.relative_to(root)
    except ValueError:
        logger.warning("[cleanup] path traversal blocked: %s -> %s", path_label, resolved)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path traversal blocked: {path_label}",
        )


def _resolve_artifact_path(relative: str) -> Path:
    """Resolve a relative path under ARTIFACTS_ROOT, with traversal protection."""
    if relative.startswith("/"):
        logger.warning("[cleanup] absolute path rejected: %s", relative)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="absolute path not allowed",
        )
    resolved = (ARTIFACTS_ROOT / relative).resolve()
    _ensure_inside_root(resolved, ARTIFACTS_ROOT, relative)
    return resolved


def _extract_task_id(relative: str) -> str | None:
    """Extract the first path segment as the task_id hint."""
    parts = relative.replace("\\", "/").strip("/").split("/")
    if parts and parts[0]:
        return parts[0]
    return None


def _target_label(key: str) -> str:
    labels = {
        "tasks": "任务工作目录",
        "downloads": "临时下载目录",
        "tmp": "临时目录",
    }
    return labels.get(key, key)


def _server_auth_kwargs(server: Server) -> dict[str, str | None]:
    if server.auth_type == "password":
        return {"key_path": None, "password": server.password}
    return {"key_path": server.key_path, "password": None}


def _server_auth_kwargs_raw(
    auth_type: str,
    password: str | None,
    key_path: str | None,
) -> dict[str, str | None]:
    if auth_type == "password":
        return {"key_path": None, "password": password}
    return {"key_path": key_path, "password": None}


# ───── Local artifacts scan (directory-aggregated) ─────


@router.get("/local-artifacts/scan", response_model=LocalArtifactsScanResult)
def scan_local_artifacts() -> LocalArtifactsScanResult:
    """
    Scan local artifacts directory.
    Returns directories grouped, with file details under each directory.
    """
    start = monotonic()
    logger.info("[cleanup] local-artifacts scan start root=%s", ARTIFACTS_ROOT)

    if not ARTIFACTS_ROOT.is_dir():
        return LocalArtifactsScanResult(
            root=str(ARTIFACTS_ROOT),
            total_dirs=0,
            total_files=0,
            total_size_bytes=0,
            items=[],
        )

    directories: list[LocalArtifactDirectory] = []
    total_files = 0
    total_size = 0

    # Gather first-level entries
    first_level: list[Path] = sorted(ARTIFACTS_ROOT.iterdir(), key=lambda p: p.name)

    for entry in first_level:
        if entry.is_dir():
            fc, sz = _build_directory_entry(entry, directories)
            total_files += fc
            total_size += sz
        # Files handled below as "未归档文件"

    # Gather root-level files -> "未归档文件" group
    root_files: list[LocalArtifactFile] = []
    root_size = 0
    root_latest_mtime: datetime | None = None

    for entry in first_level:
        if not entry.is_file():
            continue
        try:
            sz = entry.stat().st_size
            root_size += sz
            total_size += sz
            total_files += 1
            mtime = datetime.fromtimestamp(entry.stat().st_mtime) if entry.stat().st_mtime else None
            if mtime and (root_latest_mtime is None or mtime > root_latest_mtime):
                root_latest_mtime = mtime
            root_files.append(LocalArtifactFile(
                name=entry.name,
                relative_path=entry.name,
                size_bytes=sz,
                size_text=_format_size_text(sz),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    if root_files:
        directories.append(LocalArtifactDirectory(
            name="未归档文件",
            relative_path=".",
            file_count=len(root_files),
            size_bytes=root_size,
            size_text=_format_size_text(root_size),
            modified_at=root_latest_mtime,
            files=root_files,
        ))

    # Sort: "未归档文件" last, the rest by name
    directories.sort(key=lambda d: (1 if d.name == "未归档文件" else 0, d.name))

    elapsed = monotonic() - start
    logger.info(
        "[cleanup] local-artifacts scan done dirs=%d files=%d size=%d elapsed=%.3fs",
        len(directories), total_files, total_size, elapsed,
    )
    return LocalArtifactsScanResult(
        root=str(ARTIFACTS_ROOT),
        total_dirs=len(directories),
        total_files=total_files,
        total_size_bytes=total_size,
        items=directories,
    )


def _build_directory_entry(
    entry: Path,
    directories: list[LocalArtifactDirectory],
) -> tuple[int, int]:
    """Build a LocalArtifactDirectory from a first-level directory entry.
    Returns (file_count, size_bytes) for this directory.
    """
    dir_files: list[LocalArtifactFile] = []
    dir_size = 0
    dir_file_count = 0
    latest_mtime: datetime | None = None

    for f in sorted(entry.rglob("*")):
        if not f.is_file():
            continue
        try:
            sz = f.stat().st_size
            dir_size += sz
            dir_file_count += 1
            mtime = datetime.fromtimestamp(f.stat().st_mtime) if f.stat().st_mtime else None
            if mtime and (latest_mtime is None or mtime > latest_mtime):
                latest_mtime = mtime
            dir_files.append(LocalArtifactFile(
                name=f.name,
                relative_path=f.relative_to(ARTIFACTS_ROOT).as_posix(),
                size_bytes=sz,
                size_text=_format_size_text(sz),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    dir_files.sort(key=lambda x: x.name)
    task_id = entry.name if entry.name.startswith("task-") else None

    directories.append(LocalArtifactDirectory(
        name=entry.name,
        relative_path=entry.name,
        file_count=dir_file_count,
        size_bytes=dir_size,
        size_text=_format_size_text(dir_size),
        modified_at=latest_mtime,
        task_id=task_id,
        files=dir_files,
    ))
    return dir_file_count, dir_size


# ───── Local artifacts delete ─────


@router.post("/local-artifacts/delete", response_model=LocalArtifactsDeleteResponse)
def delete_local_artifacts(
    payload: LocalArtifactsDeleteRequest,
    db: Session = Depends(get_db),
) -> LocalArtifactsDeleteResponse:
    """Delete specified paths under the artifacts directory."""
    deleted: list[DeleteResultItem] = []
    failed: list[DeleteResultItem] = []

    logger.info("[cleanup] delete request paths=%s recursive=%s", payload.paths, payload.recursive)

    for relative in payload.paths:
        try:
            resolved = _resolve_artifact_path(relative)
            if not resolved.exists():
                failed.append(DeleteResultItem(path=relative, success=False, error="path not found"))
                continue

            if resolved.is_dir() and not payload.recursive:
                try:
                    if any(resolved.iterdir()):
                        failed.append(DeleteResultItem(
                            path=relative, success=False,
                            error="directory is not empty, use recursive=true",
                        ))
                        continue
                except OSError as exc:
                    failed.append(DeleteResultItem(path=relative, success=False, error=str(exc)))
                    continue

            if resolved.is_file():
                resolved.unlink()
                logger.info("[cleanup] deleted file: %s", resolved)
            elif resolved.is_dir():
                shutil.rmtree(resolved)
                logger.info("[cleanup] deleted directory: %s", resolved)
            else:
                failed.append(DeleteResultItem(path=relative, success=False, error="not a file or directory"))
                continue

            deleted.append(DeleteResultItem(path=relative, success=True))

        except HTTPException as exc:
            failed.append(DeleteResultItem(path=relative, success=False, error=exc.detail))
        except OSError as exc:
            logger.error("[cleanup] delete error: %s", exc)
            failed.append(DeleteResultItem(path=relative, success=False, error=str(exc)))

    logger.info("[cleanup] delete done deleted=%d failed=%d", len(deleted), len(failed))
    write_audit_log(
        db, action="cleanup.local_artifacts.delete", target_type="cleanup", status="success" if deleted else "failed",
        message=f"deleted {len(deleted)} local artifact dirs, {len(failed)} failed",
        detail={"paths": payload.paths, "deleted": len(deleted), "failed": len(failed)},
    )
    return LocalArtifactsDeleteResponse(deleted=deleted, failed=failed)


# ───── Remote single-server scan ─────


@router.post("/remote/scan", response_model=RemoteScanResult)
def scan_remote(
    payload: RemoteScanRequest,
    db: Session = Depends(get_db),
) -> RemoteScanResult:
    """Scan fixed remote directories on a single server."""
    start = monotonic()
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")

    logger.info("[cleanup] remote scan start server_id=%d host=%s", server.id, server.host)

    items: list[RemoteDirInfo] = []
    error: str | None = None

    executor = SSHExecutor(timeout=15)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        remote_home = executor.get_remote_home()

        for target_key in ("tasks", "downloads", "tmp"):
            raw_target = REMOTE_TARGETS[target_key]
            actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

            exists = False
            size_text = ""
            file_count = 0

            try:
                test_cmd = f"test -d {shell_quote(actual_path)}"
                exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
                exists = (exit_code == 0)

                if exists:
                    du_cmd = f"du -sh {shell_quote(actual_path)} 2>/dev/null | cut -f1"
                    size_text = executor.exec_simple(du_cmd).strip()
                    count_cmd = f"find {shell_quote(actual_path)} -type f 2>/dev/null | wc -l"
                    count_out = executor.exec_simple(count_cmd).strip()
                    file_count = int(count_out) if count_out.isdigit() else 0
            except SSHExecutorError as exc:
                logger.warning("[cleanup] remote scan target=%s error=%s", target_key, exc)

            items.append(RemoteDirInfo(
                label=_target_label(target_key),
                remote_path=actual_path,
                exists=exists,
                size_text=size_text,
                file_count=file_count,
            ))

        logger.info("[cleanup] remote scan done server_id=%d elapsed=%.3fs", server.id, monotonic() - start)

    except SSHExecutorError as exc:
        logger.error("[cleanup] remote scan failed server_id=%d error=%s", server.id, exc)
        error = str(exc)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[cleanup] remote scan unexpected error server_id=%d error=%s", server.id, exc)
        error = str(exc)
    finally:
        executor.close()

    return RemoteScanResult(server_id=server.id, items=items, error=error)


# ───── Remote scan-all (all online servers) ─────


def _scan_remote_server_worker(server_data: dict[str, Any]) -> RemoteServerScanResult:
    """Worker function to scan one remote server. Runs in thread pool."""
    server_id: int = server_data["id"]
    server_name: str = server_data["name"]
    host: str = server_data["host"]
    port: int = server_data["port"]
    username: str = server_data["username"]
    auth_type: str = server_data["auth_type"]
    password: str | None = server_data.get("password")
    key_path: str | None = server_data.get("key_path")

    directories: list[RemoteDirectoryScan] = []
    executor = SSHExecutor(timeout=15)

    try:
        executor.connect(
            host=host,
            port=port,
            username=username,
            **_server_auth_kwargs_raw(auth_type, password, key_path),
        )
        remote_home = executor.get_remote_home()

        for target_key in ("tasks", "downloads", "tmp"):
            raw_target = REMOTE_TARGETS[target_key]
            actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

            exists = False
            size_text = ""
            file_count = 0

            try:
                test_cmd = f"test -d {shell_quote(actual_path)}"
                exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
                exists = (exit_code == 0)

                if exists:
                    du_cmd = f"du -sh {shell_quote(actual_path)} 2>/dev/null | cut -f1"
                    size_text = executor.exec_simple(du_cmd).strip()
                    count_cmd = f"find {shell_quote(actual_path)} -type f 2>/dev/null | wc -l"
                    count_out = executor.exec_simple(count_cmd).strip()
                    file_count = int(count_out) if count_out.isdigit() else 0
            except SSHExecutorError:
                pass

            directories.append(RemoteDirectoryScan(
                target=target_key,
                label=_target_label(target_key),
                remote_path=actual_path,
                exists=exists,
                size_text=size_text,
                file_count=file_count,
            ))

        executor.close()
        return RemoteServerScanResult(
            server_id=server_id,
            server_name=server_name,
            host=host,
            status="success",
            directories=directories,
        )

    except Exception as exc:
        try:
            executor.close()
        except Exception:
            pass
        return RemoteServerScanResult(
            server_id=server_id,
            server_name=server_name,
            host=host,
            status="error",
            error=str(exc),
            directories=[],
        )


@router.post("/remote/scan-all", response_model=RemoteScanAllResult)
def scan_all_remote(db: Session = Depends(get_db)) -> RemoteScanAllResult:
    """Scan all online servers' remote directories concurrently."""
    servers = db.query(Server).filter(Server.status == "online").all()
    total = len(servers)

    if total == 0:
        return RemoteScanAllResult(total_servers=0, success=0, failed=0, items=[])

    # Build serializable server data dicts
    server_list: list[dict[str, Any]] = [
        {
            "id": s.id,
            "name": s.name,
            "host": s.host,
            "port": s.port,
            "username": s.username,
            "auth_type": s.auth_type,
            "password": s.password,
            "key_path": s.key_path,
        }
        for s in servers
    ]

    results: list[RemoteServerScanResult] = []
    max_workers = min(total, 10)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_remote_server_worker, sd): sd for sd in server_list}

        for future in as_completed(futures):
            sd = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                results.append(RemoteServerScanResult(
                    server_id=sd["id"],
                    server_name=sd["name"],
                    host=sd["host"],
                    status="error",
                    error=str(exc),
                ))

    success_count = sum(1 for r in results if r.status == "success")
    failed_count = sum(1 for r in results if r.status == "error")

    # Keep stable order by server_id
    results.sort(key=lambda r: r.server_id)

    return RemoteScanAllResult(
        total_servers=total,
        success=success_count,
        failed=failed_count,
        items=results,
    )


# ───── Remote single-server delete ─────


@router.post("/remote/delete", response_model=RemoteDeleteResponse)
def delete_remote(
    payload: RemoteDeleteRequest,
    db: Session = Depends(get_db),
) -> RemoteDeleteResponse:
    """Delete a fixed remote directory's contents."""
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="server not found")

    if payload.target not in REMOTE_ALLOWED_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid target: {payload.target}. allowed: {', '.join(sorted(REMOTE_ALLOWED_TARGETS))}",
        )

    raw_target = REMOTE_TARGETS[payload.target]
    logger.info(
        "[cleanup] remote delete start server_id=%d host=%s target=%s",
        server.id, server.host, payload.target,
    )

    executor = SSHExecutor(timeout=30)
    try:
        executor.connect(
            host=server.host,
            port=server.port,
            username=server.username,
            **_server_auth_kwargs(server),
        )
        remote_home = executor.get_remote_home()
        actual_path = raw_target.replace("$HOME", remote_home.rstrip("/"))

        logger.info("[cleanup] remote delete resolved path: %s", actual_path)

        test_cmd = f"test -d {shell_quote(actual_path)}"
        exit_code, _out, _err = executor.exec_capture(test_cmd, timeout_seconds=10)
        if exit_code != 0:
            msg = f"directory does not exist, nothing to delete: {actual_path}"
            logger.info("[cleanup] remote delete: %s", msg)
            write_audit_log(
                db, action="cleanup.remote.delete", target_type="cleanup", status="success",
                server_id=server.id, server_name=server.name,
                target_name=payload.target,
                message=msg,
                detail={"target": payload.target, "remote_path": actual_path, "server_id": server.id},
            )
            return RemoteDeleteResponse(
                server_id=server.id,
                target=payload.target,
                remote_path=actual_path,
                success=True,
                message=msg,
            )

        clean_cmd = f"find {shell_quote(actual_path)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +"
        logger.info("[cleanup] remote delete command: %s", clean_cmd)
        executor.exec_simple(clean_cmd)

        logger.info("[cleanup] remote delete success server_id=%d target=%s", server.id, payload.target)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="success",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"cleaned: {actual_path}",
            detail={"target": payload.target, "remote_path": actual_path, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path=actual_path,
            success=True,
            message=f"cleaned: {actual_path}",
        )

    except SSHExecutorError as exc:
        logger.error("[cleanup] remote delete failed server_id=%d target=%s error=%s", server.id, payload.target, exc)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="failed",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"SSH error: {exc}",
            detail={"target": payload.target, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path="",
            success=False,
            message=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[cleanup] remote delete unexpected error server_id=%d target=%s error=%s", server.id, payload.target, exc)
        write_audit_log(
            db, action="cleanup.remote.delete", target_type="cleanup", status="failed",
            server_id=server.id, server_name=server.name,
            target_name=payload.target,
            message=f"unexpected error: {exc}",
            detail={"target": payload.target, "server_id": server.id},
        )
        return RemoteDeleteResponse(
            server_id=server.id,
            target=payload.target,
            remote_path="",
            success=False,
            message=str(exc),
        )
    finally:
        executor.close()


# ───── Apptainer image scan (read-only) ─────

APPTAINER_DIR = BACKEND_ROOT / "apptainer"


@router.get("/apptainer/scan", response_model=ApptainerImageScanResult)
def scan_apptainer_images() -> ApptainerImageScanResult:
    """Scan the local apptainer directory for .sif files (read-only)."""
    start = monotonic()
    logger.info("[cleanup] apptainer scan start root=%s", APPTAINER_DIR)

    if not APPTAINER_DIR.is_dir():
        logger.info("[cleanup] apptainer scan done — root not found (elapsed=%.3fs)", monotonic() - start)
        return ApptainerImageScanResult(
            root=str(APPTAINER_DIR),
            total_files=0,
            total_size_bytes=0,
            items=[],
        )

    items: list[ApptainerImageItem] = []
    total_size = 0

    for entry in APPTAINER_DIR.rglob("*.sif"):
        if not entry.is_file():
            continue
        try:
            rel = entry.relative_to(APPTAINER_DIR).as_posix()
            size = entry.stat().st_size
            total_size += size
            mtime = datetime.fromtimestamp(entry.stat().st_mtime) if entry.stat().st_mtime else None
            items.append(ApptainerImageItem(
                filename=entry.name,
                relative_path=rel,
                size_bytes=size,
                size_text=_format_size_text(size),
                modified_at=mtime,
            ))
        except (OSError, ValueError):
            continue

    items.sort(key=lambda x: x.filename)

    logger.info(
        "[cleanup] apptainer scan done total_files=%d total_size=%d elapsed=%.3fs",
        len(items), total_size, monotonic() - start,
    )
    return ApptainerImageScanResult(
        root=str(APPTAINER_DIR),
        total_files=len(items),
        total_size_bytes=total_size,
        items=items,
    )
