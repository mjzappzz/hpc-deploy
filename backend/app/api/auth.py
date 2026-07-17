import logging
from time import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import ADMIN_TOKEN_EXPIRE_MINUTES, create_admin_token, decode_admin_token, require_admin_token, verify_admin_password
from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AdminVerifyRequest(BaseModel):
    password: str


class AdminVerifyResponse(BaseModel):
    expires_in: int


@router.post("/admin/verify", response_model=AdminVerifyResponse)
def admin_verify(payload: AdminVerifyRequest, response: Response, db: Session = Depends(get_db)) -> AdminVerifyResponse:
    """Verify admin password and return a short-lived admin token.

    The token expires in 5 minutes and is kept in an HttpOnly browser cookie.
    """
    if not verify_admin_password(payload.password, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员密码错误",
        )

    token = create_admin_token()
    expires_in = ADMIN_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="admin_token",
        value=token,
        max_age=expires_in,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        path="/api",
    )
    logger.info("[auth] admin token issued, expires in %ds", expires_in)
    return AdminVerifyResponse(expires_in=expires_in)


class AdminStatusResponse(BaseModel):
    expires_in: int


@router.get("/admin/status", response_model=AdminStatusResponse)
def admin_status(token: str = Depends(require_admin_token)) -> AdminStatusResponse:
    """Return remaining time for a valid admin browser session."""
    payload = decode_admin_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return AdminStatusResponse(expires_in=max(0, int(payload["exp"] - time())))


@router.post("/admin/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(response: Response) -> Response:
    """Clear the browser's admin session cookie."""
    response.delete_cookie(key="admin_token", path="/api")
    return response
