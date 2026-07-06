from datetime import datetime
from pathlib import Path

from app.core.config import settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Base(DeclarativeBase):
    pass


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None

    raw_path = database_url.removeprefix(prefix)
    if raw_path in {":memory:", ""}:
        return None

    sqlite_path = Path(raw_path)
    if not sqlite_path.is_absolute():
        sqlite_path = (BACKEND_ROOT / sqlite_path).resolve()
    return sqlite_path


def _normalize_database_url(database_url: str) -> str:
    sqlite_path = _sqlite_path(database_url)
    if sqlite_path is None:
        return database_url
    return f"sqlite:///{sqlite_path.as_posix()}"


normalized_database_url = _normalize_database_url(settings.database_url)
sqlite_path = _sqlite_path(normalized_database_url)
if sqlite_path is not None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[HPCDeploy] Using SQLite database: {sqlite_path}")

engine = create_engine(
    normalized_database_url,
    connect_args={"check_same_thread": False}
    if normalized_database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app.models import audit_log, script, server, settings as settings_model, task, task_log  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_stage5_server_columns()
    _ensure_server_auth_columns()
    _ensure_server_health_columns()
    _ensure_server_group_tags_columns()
    _ensure_stage8_task_columns()
    _ensure_batch_id_column()
    _ensure_sequence_index_column()
    _ensure_depends_on_task_id_column()
    _ensure_task_lease_columns()
    _ensure_gpu_status_column()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_stage5_server_columns() -> None:
    if not normalized_database_url.startswith("sqlite"):
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


def _ensure_server_auth_columns() -> None:
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "servers" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("servers")}
    if "password" in existing:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE servers ADD COLUMN password VARCHAR(255)"))


def _ensure_server_health_columns() -> None:
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "servers" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("servers")}
    required = {
        "last_check_at": "DATETIME",
        "last_error": "TEXT",
    }
    missing = [(name, column_type) for name, column_type in required.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(text(f"ALTER TABLE servers ADD COLUMN {name} {column_type}"))


def _ensure_server_group_tags_columns() -> None:
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "servers" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("servers")}
    required = {
        "group_name": "VARCHAR(50) DEFAULT '默认分组'",
        "tags_json": "TEXT DEFAULT '[]'",
    }
    missing = [(name, col_type) for name, col_type in required.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as connection:
        for name, col_type in missing:
            connection.execute(text(f"ALTER TABLE servers ADD COLUMN {name} {col_type}"))


def _ensure_stage8_task_columns() -> None:
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("tasks")}
    required_columns = {
        "task_type",
        "file_path",
        "file_name",
        "display_category",
        "remote_work_dir",
        "command_preview",
    }
    script_id_nullable = columns.get("script_id", {}).get("nullable", True)
    if required_columns.issubset(columns.keys()) and script_id_nullable:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tasks_stage8 (
                    id INTEGER NOT NULL PRIMARY KEY,
                    task_id VARCHAR(100) NOT NULL UNIQUE,
                    server_id INTEGER NOT NULL,
                    script_id INTEGER,
                    task_type VARCHAR(20),
                    file_path VARCHAR(255),
                    file_name VARCHAR(255),
                    display_category VARCHAR(50),
                    remote_work_dir TEXT,
                    command_preview TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                    params JSON,
                    start_time DATETIME,
                    end_time DATETIME,
                    exit_code INTEGER,
                    error_message TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(server_id) REFERENCES servers (id),
                    FOREIGN KEY(script_id) REFERENCES scripts (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO tasks_stage8 (
                    id, task_id, server_id, script_id, task_type, file_path, file_name,
                    display_category, remote_work_dir, command_preview, status, params,
                    start_time, end_time, exit_code, error_message, created_at, updated_at
                )
                SELECT
                    id,
                    task_id,
                    server_id,
                    script_id,
                    NULL AS task_type,
                    NULL AS file_path,
                    NULL AS file_name,
                    NULL AS display_category,
                    NULL AS remote_work_dir,
                    NULL AS command_preview,
                    status,
                    params,
                    start_time,
                    end_time,
                    exit_code,
                    error_message,
                    created_at,
                    updated_at
                FROM tasks
                """
            )
        )
        connection.execute(text("DROP TABLE tasks"))
        connection.execute(text("ALTER TABLE tasks_stage8 RENAME TO tasks"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_id ON tasks (id)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tasks_task_id ON tasks (task_id)"))


def _ensure_batch_id_column() -> None:
    """Phase 26A: Add batch_id column to tasks table for batch grouping."""
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "batch_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN batch_id TEXT"))
    print("[HPCDeploy] Added batch_id column to tasks table")


def _ensure_sequence_index_column() -> None:
    """Add sequence_index column to tasks table for stress suite ordering."""
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "sequence_index" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN sequence_index INTEGER"))
    print("[HPCDeploy] Added sequence_index column to tasks table")


def _ensure_depends_on_task_id_column() -> None:
    """Add depends_on_task_id column to tasks table for task dependency tracking."""
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "depends_on_task_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN depends_on_task_id TEXT"))
    print("[HPCDeploy] Added depends_on_task_id column to tasks table")


def _ensure_task_lease_columns() -> None:
    """Add task lease / heartbeat columns for startup recovery."""
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("tasks")}
    required = {
        "last_heartbeat": "DATETIME",
        "worker_id": "VARCHAR(100)",
        "lease_expire_time": "DATETIME",
    }
    missing = [(name, column_type) for name, column_type in required.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {column_type}"))
    print("[HPCDeploy] Added task lease columns to tasks table")


def _ensure_gpu_status_column() -> None:
    """Phase 28B: Add gpu_status column to servers table for GPU detection accuracy."""
    if not normalized_database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "servers" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("servers")}
    if "gpu_status" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE servers ADD COLUMN gpu_status VARCHAR(20)"))
    print("[HPCDeploy] Added gpu_status column to servers table")

