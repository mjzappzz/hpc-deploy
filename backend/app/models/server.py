import json
from datetime import datetime

from app.db.database import Base
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
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
    gpu_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cpu_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    disk_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_name: Mapped[str] = mapped_column(String(50), default="默认分组", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @hybrid_property
    def tags(self) -> list[str]:
        """Deserialize tags_json as a list of strings."""
        if not self.tags_json:
            return []
        try:
            val = json.loads(self.tags_json)
            if isinstance(val, list):
                return val
            return []
        except (json.JSONDecodeError, TypeError):
            return []
