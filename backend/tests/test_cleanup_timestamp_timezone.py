import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cleanup import scan_local_artifacts
from app.db.database import Base
from app.models.task import Task


class CleanupTimestampTimezoneTests(unittest.TestCase):
    def test_local_artifact_mtime_is_returned_as_naive_utc(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                root = Path(tmp_dir)
                task_dir = root / "task-20260717-000000-test"
                task_dir.mkdir()
                artifact = task_dir / "result.log"
                artifact.write_text("ok", encoding="utf-8")
                epoch = 1_784_000_000
                artifact.touch()
                __import__("os").utime(artifact, (epoch, epoch))

                with patch("app.api.cleanup.ARTIFACTS_ROOT", root):
                    result = scan_local_artifacts(db)

            returned = result.items[0].files[0].modified_at
            expected = datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)
            self.assertEqual(returned, expected)
        finally:
            db.close()

    def test_matched_task_uses_completion_time_instead_of_file_touch_time(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            task_id = "task-20260710-203433-test"
            completed_at = datetime(2026, 7, 10, 12, 42, 12)
            db.add(Task(task_id=task_id, server_id=1, status="SUCCESS", created_at=completed_at, end_time=completed_at))
            db.commit()
            with tempfile.TemporaryDirectory() as tmp_dir:
                root = Path(tmp_dir)
                task_dir = root / task_id
                task_dir.mkdir()
                (task_dir / "result.log").write_text("ok", encoding="utf-8")

                with patch("app.api.cleanup.ARTIFACTS_ROOT", root):
                    result = scan_local_artifacts(db)

            self.assertEqual(result.items[0].modified_at, completed_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
