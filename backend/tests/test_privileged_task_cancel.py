import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.tasks import _cancel_remote_process
from app.core.ssh_executor import SSHExecutorError


class PrivilegedTaskCancelTests(unittest.TestCase):
    def test_root_gpu_process_group_is_stopped_with_saved_sudo_credential(self) -> None:
        task = SimpleNamespace(
            task_id="task-gpu", task_type="gpu_driver", server_id=132, batch_id=None,
            remote_work_dir="/tmp/gpu-job", file_name="nvidia-linux-driver.run",
        )
        db = Mock()
        db.get.return_value = SimpleNamespace(password="private-sudo-password")
        executor = Mock()
        executor.exec_simple.return_value = "1000"
        executor.exec_capture.side_effect = [
            (0, "", ""), (0, "12345", ""), (0, "12345", ""),
        ]
        executor.exec_sudo.return_value = (0, "", "")

        with patch("app.api.tasks._add_task_log"):
            _cancel_remote_process(executor, task, db)

        self.assertIn(".gpu-driver.pid", executor.exec_capture.call_args_list[1].args[0])
        command = executor.exec_sudo.call_args.args[0]
        self.assertIn("kill -TERM", command)
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "private-sudo-password")
        self.assertNotIn("private-sudo-password", command)

    def test_cuda_cancel_without_confirmed_pid_does_not_claim_remote_stopped(self) -> None:
        task = SimpleNamespace(
            task_id="task-cuda", task_type="cuda_toolkit", server_id=132, batch_id=None,
            remote_work_dir="/tmp/cuda-job", file_name="cuda-toolkit-install.sh",
        )
        db = Mock()
        db.get.return_value = SimpleNamespace(password="private-sudo-password")
        executor = Mock()
        executor.exec_simple.return_value = "1000"
        executor.exec_capture.side_effect = [(0, "", ""), (0, "", "")]

        with patch("app.api.tasks._add_task_log"), self.assertRaisesRegex(
            SSHExecutorError, "remote process not confirmed"
        ):
            _cancel_remote_process(executor, task, db)
        executor.exec_sudo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
