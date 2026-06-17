from pathlib import Path

from app.core.config import settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    pass


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None

    raw_path = database_url.removeprefix(prefix)
    if raw_path in {":memory:", ""}:
        return None

    return Path(raw_path)


sqlite_path = _sqlite_path(settings.database_url)
if sqlite_path is not None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app.models import script, server, task, task_log  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_stage5_server_columns()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_stage5_server_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "servers" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("servers")}
    required = {
        "cpu_info": "TEXT",
        "memory_info": "TEXT",
        "disk_info": "TEXT",
        "network_info": "TEXT",
    }
    missing = [(name, column_type) for name, column_type in required.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(text(f"ALTER TABLE servers ADD COLUMN {name} {column_type}"))
