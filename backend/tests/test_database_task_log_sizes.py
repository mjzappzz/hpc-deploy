import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cleanup import scan_database_task_log_sizes
from app.db.database import Base
from app.models.task_log import TaskLog


class DatabaseTaskLogSizesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add_all([
            TaskLog(task_id="task-large", level="INFO", message="中文日志", created_at=datetime(2026, 7, 17, 12, 0, 0)),
            TaskLog(task_id="task-large", level="INFO", message="abcd", created_at=datetime(2026, 7, 17, 12, 1, 0)),
            TaskLog(task_id="task-small", level="INFO", message="ok", created_at=datetime(2026, 7, 17, 11, 0, 0)),
        ])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_scan_aggregates_log_content_bytes_by_task_descending(self) -> None:
        result = scan_database_task_log_sizes(db=self.session)

        self.assertEqual(result.total_tasks, 2)
        self.assertEqual([item.task_id for item in result.items], ["task-large", "task-small"])
        self.assertEqual(result.items[0].log_count, 2)
        self.assertEqual(result.items[0].message_bytes, len("中文日志".encode("utf-8")) + 4)
        self.assertEqual(result.items[1].message_bytes, 2)


if __name__ == "__main__":
    unittest.main()
