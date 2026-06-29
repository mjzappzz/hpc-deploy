import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.auth import create_admin_token, verify_admin_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AdminVerifyRequest(BaseModel):
    password: str


class AdminVerifyResponse(BaseModel):
    admin_token: str
    expires_in: int


@router.post("/admin/verify", response_model=AdminVerifyResponse)
def admin_verify(payload: AdminVerifyRequest) -> AdminVerifyResponse:
    """Verify admin password and return a short-lived admin token.

    The token expires in 5 minutes (300 seconds). Subsequent admin
    operations must include the token via the X-Admin-Token header.
    """
    if not verify_admin_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员密码错误",
        )

    token = create_admin_token()
    logger.info("[auth] admin token issued, expires in %ds", 300)
    return AdminVerifyResponse(admin_token=token, expires_in=300)
