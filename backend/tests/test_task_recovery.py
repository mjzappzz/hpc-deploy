from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest

from app.core.task_recovery import _is_stale, _reset_task_to_pending, should_requeue_after_restart
from app.core.task_runner import _build_remote_execution_command


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

    def test_restart_requeues_pre_execution_stages_even_with_a_fresh_lease(self) -> None:
        self.assertTrue(should_requeue_after_restart("CONNECTING", is_stale=False))
        self.assertTrue(should_requeue_after_restart("PREPARING", is_stale=False))
        self.assertTrue(should_requeue_after_restart("UPLOADING", is_stale=False))
        self.assertFalse(should_requeue_after_restart("RUNNING", is_stale=False))

    def test_restart_never_requeues_a_running_remote_task_even_when_stale(self) -> None:
        self.assertFalse(should_requeue_after_restart("RUNNING", is_stale=True))

    def test_remote_command_persists_exit_code_for_restart_recovery(self) -> None:
        command = _build_remote_execution_command("bash ./install.sh", "/tmp/task/.hpcdeploy.pid")

        self.assertIn(".hpcdeploy.exit_code", command)


if __name__ == "__main__":
    unittest.main()
