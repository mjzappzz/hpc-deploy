import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cleanup import scan_database_task_log_sizes
from app.db.database import Base
from app.models.server import Server
from app.models.task import Task
from app.models.task_log import TaskLog


class DatabaseTaskLogSizesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add_all([
            Server(id=1, name="compute-01", host="10.0.0.1", username="root"),
            Task(task_id="task-large", server_id=1, status="SUCCESS", batch_id="batch-stress-001"),
            Task(task_id="task-small", server_id=1, status="SUCCESS"),
            TaskLog(task_id="task-large", level="INFO", message="中文日志", created_at=datetime(2026, 7, 17, 12, 0, 0)),
            TaskLog(task_id="task-large", level="INFO", message="abcd", created_at=datetime(2026, 7, 17, 12, 1, 0)),
            TaskLog(task_id="task-small", level="INFO", message="ok", created_at=datetime(2026, 7, 17, 11, 0, 0)),
            TaskLog(task_id="batch-summary-001", level="INFO", message="batch created", created_at=datetime(2026, 7, 17, 10, 0, 0)),
        ])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_scan_aggregates_log_content_bytes_by_task_descending(self) -> None:
        result = scan_database_task_log_sizes(db=self.session)

        self.assertEqual(result.total_tasks, 3)
        self.assertEqual(result.items[0].task_id, "task-large")
        self.assertEqual(result.items[0].log_count, 2)
        self.assertEqual(result.items[0].message_bytes, len("中文日志".encode("utf-8")) + 4)
        self.assertTrue(result.items[0].is_batch_task)
        self.assertEqual(result.items[0].batch_id, "batch-stress-001")
        self.assertEqual(result.items[0].server_name, "compute-01")
        items = {item.task_id: item for item in result.items}
        self.assertEqual(items["task-small"].message_bytes, 2)
        self.assertFalse(items["task-small"].is_batch_task)
        self.assertIsNone(items["task-small"].batch_id)
        self.assertEqual(items["task-small"].server_name, "compute-01")
        self.assertTrue(items["batch-summary-001"].is_batch_task)
        self.assertEqual(items["batch-summary-001"].batch_id, "batch-summary-001")


if __name__ == "__main__":
    unittest.main()
