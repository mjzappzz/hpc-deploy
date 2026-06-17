from datetime import datetime
from typing import Any

from app.db.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

