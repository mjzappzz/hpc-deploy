from datetime import datetime

from app.db.database import Base
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(100), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), default="key", nullable=False)
    key_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    os_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    cpu_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    disk_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
