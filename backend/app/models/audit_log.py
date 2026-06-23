from datetime import datetime

from app.db.database import Base
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class AuditLog(Base):
    """Operation audit log."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="local-admin")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    server_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    server_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success", index=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
