import logging
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


class AdminTemporarySessionRequest(BaseModel):
    tab_id: str

    @field_validator("tab_id")
    @classmethod
    def validate_tab_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 128:
            raise ValueError("invalid admin tab id")
        return normalized


class AdminVerifyResponse(BaseModel):
    expires_in: int | None


class AdminSessionGrant(AdminVerifyResponse):
    token: str


TEMPORARY_ADMIN_SESSION_MINUTES = 1


def should_secure_admin_cookie(request: Request) -> bool:
    return request.url.scheme.lower() == "https"


def temporary_admin_session_enabled() -> bool:
    return settings.app_env == "development" or settings.hpcdeploy_temporary_admin_mode_enabled


def issue_temporary_admin_session(tab_id: str) -> AdminSessionGrant:
    """Issue the fixed, short-lived administrator grant when explicitly enabled."""
    if not temporary_admin_session_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return AdminSessionGrant(
        expires_in=TEMPORARY_ADMIN_SESSION_MINUTES * 60,
        token=create_admin_token(duration_minutes=TEMPORARY_ADMIN_SESSION_MINUTES, tab_id=tab_id),
    )


def set_admin_session_cookie(response: Response, *, token: str, expires_in: int | None, request: Request) -> None:
    cookie_kwargs: dict[str, str | int | bool] = {
        "key": "admin_token",
        "value": token,
        "httponly": True,
        "samesite": "lax",
        "secure": should_secure_admin_cookie(request),
        "path": "/api",
    }
    if expires_in is not None:
        cookie_kwargs["max_age"] = expires_in
    response.set_cookie(**cookie_kwargs)


@router.post("/admin/verify", response_model=AdminVerifyResponse)
def admin_verify(
    payload: AdminVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminVerifyResponse:
    """Verify password and issue an HttpOnly admin token for one browser tab."""
    if not verify_admin_password(payload.password, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员密码错误",
        )

    token = create_admin_token(duration_minutes=payload.duration_minutes, tab_id=payload.tab_id)
    expires_in = payload.duration_minutes * 60 if payload.duration_minutes is not None else None
    set_admin_session_cookie(response, token=token, expires_in=expires_in, request=request)
    logger.info("[auth] admin token issued, expires_in=%s", expires_in)
    return AdminVerifyResponse(expires_in=expires_in)


@router.get("/admin/temporary-session-available")
def get_temporary_admin_session_availability() -> dict[str, bool]:
    return {"enabled": temporary_admin_session_enabled()}


@router.post("/admin/temporary-session", response_model=AdminVerifyResponse)
def admin_temporary_session(
    payload: AdminTemporarySessionRequest,
    request: Request,
    response: Response,
) -> AdminVerifyResponse:
    """Create the fixed one-minute passwordless administrator grant when enabled."""
    grant = issue_temporary_admin_session(payload.tab_id)
    set_admin_session_cookie(response, token=grant.token, expires_in=grant.expires_in, request=request)
    logger.warning("[auth] temporary passwordless admin token issued, expires_in=%s", grant.expires_in)
    return AdminVerifyResponse(expires_in=grant.expires_in)


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
