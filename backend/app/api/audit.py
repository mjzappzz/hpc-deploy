import json
import logging
from datetime import datetime

from app.core.auth import require_admin_token
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogItem, AuditLogPage
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-logs", tags=["audit"])

# Operations that change credentials, configuration, remote access, or delete data.
# The UI uses this as its default view while the complete audit stream remains available.
HIGH_RISK_AUDIT_ACTIONS = {
    "auto_cleanup_local_artifacts",
    "cleanup.local_artifacts.delete",
    "cleanup.remote.delete",
    "script.delete",
    "script.upload",
    "server.delete",
    "server.deploy_public_key",
    "server.deploy_public_key_all",
    "settings.change_password",
    "settings.update",
    "task.batch_cancel",
    "task.cancel",
    "task.delete",
}


def _row_to_item(row: AuditLog) -> AuditLogItem:
    """Convert ORM row to response item, parsing detail_json."""
    detail = None
    if row.detail_json:
        try:
            detail = json.loads(row.detail_json)
        except (json.JSONDecodeError, TypeError):
            detail = row.detail_json
    return AuditLogItem(
        id=row.id,
        created_at=row.created_at,
        actor=row.actor,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        target_name=row.target_name,
        server_id=row.server_id,
        server_name=row.server_name,
        task_id=row.task_id,
        status=row.status,
        message=row.message,
        detail_json=detail,
        client_ip=row.client_ip,
    )


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    risk_only: bool = Query(False),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> AuditLogPage:
    """List audit logs with pagination and filtering."""

    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if status:
        query = query.filter(AuditLog.status == status)
    if risk_only:
        query = query.filter(AuditLog.action.in_(HIGH_RISK_AUDIT_ACTIONS))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            AuditLog.target_name.ilike(like)
            | AuditLog.server_name.ilike(like)
            | AuditLog.task_id.ilike(like)
            | AuditLog.message.ilike(like)
            | AuditLog.action.ilike(like)
        )
    if start_time:
        try:
            dt = datetime.fromisoformat(start_time)
            query = query.filter(AuditLog.created_at >= dt)
        except ValueError:
            pass
    if end_time:
        try:
            dt = datetime.fromisoformat(end_time)
            query = query.filter(AuditLog.created_at <= dt)
        except ValueError:
            pass

    total = query.count()

    rows = (
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogPage(
        items=[_row_to_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
