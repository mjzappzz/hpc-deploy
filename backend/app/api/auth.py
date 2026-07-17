import logging
from time import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.auth import ADMIN_SESSION_DURATION_MINUTES, create_admin_token, decode_admin_token, require_admin_token, verify_admin_password
from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AdminVerifyRequest(BaseModel):
    password: str
    duration_minutes: int | None = 5
    tab_id: str

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, value: int | None) -> int | None:
        if value is not None and value not in ADMIN_SESSION_DURATION_MINUTES:
            raise ValueError("管理员模式时长仅支持 5、15、30、60 分钟或本标签页持续")
        return value

    @field_validator("tab_id")
    @classmethod
    def validate_tab_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 128:
            raise ValueError("invalid admin tab id")
        return normalized


class AdminVerifyResponse(BaseModel):
    expires_in: int | None


@router.post("/admin/verify", response_model=AdminVerifyResponse)
def admin_verify(payload: AdminVerifyRequest, response: Response, db: Session = Depends(get_db)) -> AdminVerifyResponse:
    """Verify password and issue an HttpOnly admin token for one browser tab."""
    if not verify_admin_password(payload.password, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员密码错误",
        )

    token = create_admin_token(duration_minutes=payload.duration_minutes, tab_id=payload.tab_id)
    expires_in = payload.duration_minutes * 60 if payload.duration_minutes is not None else None
    cookie_kwargs = {
        "key": "admin_token",
        "value": token,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env == "production",
        "path": "/api",
    }
    if expires_in is not None:
        cookie_kwargs["max_age"] = expires_in
    response.set_cookie(**cookie_kwargs)
    logger.info("[auth] admin token issued, expires_in=%s", expires_in)
    return AdminVerifyResponse(expires_in=expires_in)


class AdminStatusResponse(BaseModel):
    expires_in: int | None


@router.get("/admin/status", response_model=AdminStatusResponse)
def admin_status(token: str = Depends(require_admin_token)) -> AdminStatusResponse:
    """Return remaining time for a valid admin browser session."""
    payload = decode_admin_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    expire = payload.get("exp")
    return AdminStatusResponse(expires_in=max(0, int(expire - time())) if expire is not None else None)


@router.post("/admin/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(response: Response) -> Response:
    """Clear the browser's admin session cookie."""
    response.delete_cookie(key="admin_token", path="/api")
    return response
