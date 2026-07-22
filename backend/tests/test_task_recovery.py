from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.core.task_recovery import _is_stale, _reset_task_to_pending, should_requeue_after_restart
from app.core import task_runner
from app.core.task_runner import _build_remote_execution_command


class TaskRecoveryTests(unittest.TestCase):
    def test_boot_id_change_is_an_unexpected_reboot_for_stress_tasks(self) -> None:
        self.assertTrue(task_runner._has_unexpected_server_reboot("boot-before", "boot-after"))
        self.assertFalse(task_runner._has_unexpected_server_reboot("boot-before", "boot-before"))
        self.assertFalse(task_runner._has_unexpected_server_reboot("", "boot-after"))

    @patch("app.core.task_runner._broadcast_done_safe")
    @patch("app.core.task_runner.schedule_report_summary_generation")
    @patch("app.core.task_runner._add_log")
    def test_unexpected_reboot_cancels_unstarted_following_batch_tasks(
        self,
        add_log: Mock,
        schedule_summary: Mock,
        broadcast_done: Mock,
    ) -> None:
        class FakeQuery:
            def __init__(self, rows) -> None:
                self.rows = rows

            def filter(self, *_args):
                return self

            def order_by(self, *_args):
                return self

            def all(self):
                return self.rows

        class FakeDb:
            def __init__(self, rows) -> None:
                self.rows = rows
                self.commits = 0

            def query(self, _model):
                return FakeQuery(self.rows)

            def commit(self) -> None:
                self.commits += 1

        current = SimpleNamespace(
            id=10,
            task_id="task-current",
            batch_id="batch-1",
            server_id=8,
            sequence_index=2,
        )
        follower = SimpleNamespace(
            task_id="task-follower",
            status="PENDING",
            end_time=None,
            exit_code=None,
            error_message=None,
            worker_id="worker-1",
            lease_expire_time=datetime.utcnow(),
        )
        db = FakeDb([follower])

        task_runner._cancel_following_stress_batch_tasks(
            db,
            current,
            "server rebooted unexpectedly during previous stress task",
        )

        self.assertEqual(follower.status, "CANCELED")
        self.assertEqual(follower.exit_code, -15)
        self.assertIn("server rebooted unexpectedly", follower.error_message)
        self.assertEqual(db.commits, 1)
        schedule_summary.assert_called_once_with("task-follower")
        broadcast_done.assert_called_once_with("task-follower", "CANCELED")
        self.assertTrue(add_log.called)

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

    @patch("app.core.task_runner._schedule_stress_recovery_retry")
    @patch("app.core.task_runner._fail_running_stress_task")
    @patch("app.core.task_runner._add_log")
    @patch("app.core.task_runner.SSHExecutor")
    @patch("app.core.task_runner.SessionLocal")
    def test_recovery_ssh_connect_failure_keeps_stress_task_running_for_retry(
        self,
        session_local: Mock,
        executor_cls: Mock,
        add_log: Mock,
        fail_task: Mock,
        schedule_retry: Mock,
    ) -> None:
        task = SimpleNamespace(task_id="task-recovery-ssh", server_id=14, status="RUNNING")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = task
        db.get.return_value = SimpleNamespace(host="10.0.0.1", port=22, username="root", key_path=None, password=None)
        session_local.return_value = db
        executor_cls.return_value.connect.side_effect = OSError(1, "Operation not permitted")

        task_runner._stress_recovery_monitor(task.task_id)

        fail_task.assert_not_called()
        self.assertEqual(task.status, "RUNNING")
        schedule_retry.assert_called_once_with(task.task_id)
        self.assertTrue(any(call.args[2] == "WARNING" for call in add_log.call_args_list))


if __name__ == "__main__":
    unittest.main()
