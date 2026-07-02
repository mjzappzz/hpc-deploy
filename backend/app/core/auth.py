import logging
import os
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Admin password from environment ──

ADMIN_PASSWORD: str = os.environ.get("HPCDEPLOY_ADMIN_PASSWORD", "admin123")
if ADMIN_PASSWORD == "admin123":
    logger.warning(
        "[auth] HPCDEPLOY_ADMIN_PASSWORD 使用默认值 admin123！"
        " 生产环境请设置环境变量 HPCDEPLOY_ADMIN_PASSWORD"
    )


def verify_admin_password(password: str, db: Session | None = None) -> bool:
    """Validate the provided password.

    Priority:
    1. DB-stored admin_password (if db is provided and key exists)
    2. Environment variable HPCDEPLOY_ADMIN_PASSWORD
    """
    if db is not None:
        from app.models.settings import SystemSetting
        row = db.get(SystemSetting, "admin_password")
        if row is not None and row.value:
            return password == row.value
    return password == ADMIN_PASSWORD


# ── Short-lived admin token (JWT, 5 min) ──

ALGORITHM = "HS256"
ADMIN_TOKEN_EXPIRE_MINUTES = 5


def create_admin_token() -> str:
    """Create a short-lived JWT for admin operation authorization."""
    expire = datetime.utcnow() + timedelta(minutes=ADMIN_TOKEN_EXPIRE_MINUTES)
    payload: dict = {"scope": "admin", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_admin_token(token: str) -> dict | None:
    """Decode and validate an admin token. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("scope") != "admin":
            logger.warning("[auth] admin token missing scope")
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("[auth] admin token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("[auth] invalid admin token")
        return None


# ── Dependency: require admin token via X-Admin-Token header ──


def require_admin_token(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
) -> str:
    """Require a valid admin token. Raises 403 if missing or invalid."""
    if x_admin_token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    payload = decode_admin_token(x_admin_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return x_admin_token
