import json
import logging
from typing import Any

from app.models.audit_log import AuditLog
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Sensitive fields that must never appear in audit details ──

SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "password",
    "private_key",
    "private_key_content",
    "public_key_content",
    "secret",
    "token",
    "command",
    "raw_shell",
    "raw_args",
    "env",
})


def _sanitize_detail(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    """Replace sensitive field values with '***'."""
    if not detail:
        return detail
    sanitized: dict[str, Any] = {}
    for key, value in detail.items():
        if key in SENSITIVE_FIELDS:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def write_audit_log(
    db: Session,
    action: str,
    target_type: str,
    status: str,
    actor: str = "system",
    target_id: str | None = None,
    target_name: str | None = None,
    server_id: int | None = None,
    server_name: str | None = None,
    task_id: str | None = None,
    message: str | None = None,
    detail: dict[str, Any] | None = None,
    client_ip: str | None = None,
) -> None:
    """Write an operation audit log entry.

    This function catches all exceptions internally — audit failures
    MUST NOT affect the main business operation.
    """
    try:
        sanitized_detail = _sanitize_detail(detail)
        entry = AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            server_id=server_id,
            server_name=server_name,
            task_id=task_id,
            status=status,
            message=message,
            detail_json=json.dumps(sanitized_detail, ensure_ascii=False)
            if sanitized_detail
            else None,
            client_ip=client_ip,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("[audit] failed to write audit log (action=%s, status=%s)", action, status, exc_info=True)
