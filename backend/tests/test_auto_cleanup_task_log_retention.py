import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auto_cleanup import run_local_artifacts_auto_cleanup
from app.db.database import Base
from app.models.task import Task
from app.models.task_log import TaskLog


class AutoCleanupTaskLogRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.now = datetime.now()

    def tearDown(self) -> None:
        self.db.close()

    def test_uses_terminal_task_time_for_artifacts_and_task_logs(self) -> None:
        old_task = Task(
            task_id="task-old", server_id=1, status="SUCCESS",
            created_at=self.now - timedelta(days=40), end_time=self.now - timedelta(days=40),
        )
        recent_task = Task(
            task_id="task-recent", server_id=1, status="SUCCESS",
            created_at=self.now - timedelta(days=1), end_time=self.now - timedelta(days=1),
        )
        active_task = Task(
            task_id="task-active", server_id=1, status="RUNNING",
            created_at=self.now - timedelta(days=40),
        )
        self.db.add_all([old_task, recent_task, active_task])
        self.db.add_all([
            TaskLog(task_id="task-old", level="INFO", message="old"),
            TaskLog(task_id="task-recent", level="INFO", message="recent"),
            TaskLog(task_id="task-active", level="INFO", message="active"),
        ])
        self.db.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for task_id in ("task-old", "task-recent", "task-active"):
                directory = root / task_id
                directory.mkdir()
                (directory / "result.txt").write_text(task_id, encoding="utf-8")

            with patch("app.core.auto_cleanup.ARTIFACTS_DIR", root), \
                 patch("app.core.auto_cleanup._write_dir_audit"), \
                 patch("app.core.auto_cleanup._write_summary_audit"), \
                 patch("app.core.auto_cleanup._save_result"):
                result = run_local_artifacts_auto_cleanup(self.db, retention_days=30)

            self.assertFalse((root / "task-old").exists())
            self.assertTrue((root / "task-recent").exists())
            self.assertTrue((root / "task-active").exists())

        remaining_task_ids = {row.task_id for row in self.db.query(TaskLog).all()}
        self.assertNotIn("task-old", remaining_task_ids)
        self.assertIn("task-recent", remaining_task_ids)
        self.assertIn("task-active", remaining_task_ids)
        self.assertEqual(result.deleted_log_rows, 1)


if __name__ == "__main__":
    unittest.main()
