from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest

from app.core.task_recovery import _is_stale, _reset_task_to_pending


class TaskRecoveryTests(unittest.TestCase):
    def test_expired_lease_is_stale(self) -> None:
        now = datetime.utcnow()
        task = SimpleNamespace(
            lease_expire_time=now - timedelta(seconds=1),
            last_heartbeat=now,
            updated_at=now,
        )

        self.assertTrue(_is_stale(task, now, timedelta(seconds=600)))

    def test_reset_task_to_pending_clears_scheduler_failure(self) -> None:
        now = datetime.utcnow()
        task = SimpleNamespace(
            status="FAILED",
            worker_id="worker-1",
            lease_expire_time=now,
            last_heartbeat=now,
            start_time=now,
            end_time=now,
            exit_code=1,
            error_message="stress suite scheduler recovered orphaned PENDING task after backend restart",
            updated_at=now,
        )

        _reset_task_to_pending(task, now, "reset")

        self.assertEqual(task.status, "PENDING")
        self.assertIsNone(task.worker_id)
        self.assertIsNone(task.lease_expire_time)
        self.assertIsNone(task.last_heartbeat)
        self.assertIsNone(task.start_time)
        self.assertIsNone(task.end_time)
        self.assertIsNone(task.exit_code)
        self.assertIsNone(task.error_message)


if __name__ == "__main__":
    unittest.main()
