import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cleanup import scan_local_logs
from app.db.database import Base
from app.models.task_log import TaskLog


class LocalLogsScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add_all([
            TaskLog(
                task_id="task-larger",
                level="ERROR",
                message="中文日志",
                created_at=datetime(2026, 7, 17, 12, 0, 0),
            ),
            TaskLog(
                task_id="task-smaller",
                level="INFO",
                message="ok",
                created_at=datetime(2026, 7, 17, 11, 0, 0),
            ),
        ])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_scan_lists_database_log_rows_with_utf8_payload_size(self) -> None:
        result = scan_local_logs(db=self.session, limit=100)

        self.assertEqual(result.mode, "database")
        self.assertEqual(result.total_logs, 2)
        self.assertEqual(result.returned_logs, 2)
        self.assertEqual([item.task_id for item in result.items], ["task-larger", "task-smaller"])
        self.assertEqual(result.items[0].message_bytes, len("中文日志".encode("utf-8")))
        self.assertEqual(result.items[1].message_bytes, 2)
        self.assertEqual(result.total_message_bytes, len("中文日志".encode("utf-8")) + 2)


if __name__ == "__main__":
    unittest.main()
