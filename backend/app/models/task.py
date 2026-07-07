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
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remote_work_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    sequence_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depends_on_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expire_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hidden_from_history: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hidden_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TaskReportSummary(Base):
    __tablename__ = "task_report_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    report_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
