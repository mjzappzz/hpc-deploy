from pathlib import Path
import subprocess
import tempfile

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.api.tasks import MANAGED_SUITE_ACTIONS, _build_managed_suite_batch_ids, _managed_suite_effective_tasks
from app.core import task_runner
from app.core.task_runner import _script_command
from app.schemas.task import GpuDriverBatchRunRequest, GpuDriverRunRequest, ManagedSuiteCreateRequest


class ManagedSuiteContractTests(unittest.TestCase):
    def test_each_server_gets_an_independent_batch(self) -> None:
        tokens = iter(["server-a", "server-b"])

        batch_ids = _build_managed_suite_batch_ids(
            [101, 202],
            now_str="20260730-180000",
            token_factory=lambda: next(tokens),
        )

        self.assertEqual(
            batch_ids,
            {
                101: "batch-20260730-180000-server-a",
                202: "batch-20260730-180000-server-b",
            },
        )

    def test_base_system_order_is_fixed(self) -> None:
        self.assertEqual(
            [action for action, _path in MANAGED_SUITE_ACTIONS["base_system"]],
            ["disable_lock_sleep", "lock_release"],
        )

    def test_gpu_install_order_is_fixed(self) -> None:
        request = ManagedSuiteCreateRequest(
            suite_type="gpu_software",
            server_ids=[1, 2],
            actions=["gpu_driver", "cuda_toolkit"],
            driver_type="datacenter",
            driver_id="a" * 24,
        )

        self.assertEqual(request.actions, ["gpu_driver", "cuda_toolkit"])
        self.assertEqual(
            [action for action, _path in MANAGED_SUITE_ACTIONS["gpu_software"]],
            request.actions,
        )

    def test_kernel_maintenance_is_disabled_when_gpu_request_omits_it(self) -> None:
        single = GpuDriverRunRequest(
            server_id=1,
            driver_type="geforce",
            driver_id="a" * 24,
        )
        batch = GpuDriverBatchRunRequest(
            server_ids=[1, 2],
            driver_type="geforce",
            driver_id="a" * 24,
        )
        suite = ManagedSuiteCreateRequest(
            suite_type="gpu_software",
            server_ids=[1],
            actions=["gpu_driver", "cuda_toolkit"],
            driver_type="geforce",
            driver_id="a" * 24,
        )

        self.assertFalse(single.allow_kernel_maintenance)
        self.assertFalse(batch.allow_kernel_maintenance)
        self.assertFalse(suite.allow_kernel_maintenance)

    def test_managed_suite_retry_replaces_the_failed_step_for_scheduling(self) -> None:
        tasks = [
            SimpleNamespace(id=1, task_id="task-first", sequence_index=1, params={}, status="SUCCESS"),
            SimpleNamespace(id=2, task_id="task-failed", sequence_index=2, params={}, status="FAILED"),
            SimpleNamespace(
                id=3, task_id="task-retry", sequence_index=3,
                params={"__retry_of_task_id": "task-failed"}, status="PENDING",
            ),
        ]

        effective = _managed_suite_effective_tasks(tasks)

        self.assertEqual([task.task_id for task in effective], ["task-first", "task-retry"])


    def test_base_system_batch_uses_sudo_stdin_without_logging_password(self) -> None:
        for name in ("disable_linux_lock_sleep.sh", "lock_linux_release.sh"):
            task = SimpleNamespace(
                file_name=name, file_path=f"scripts/mpi/{name}", task_type="script", server_id=132,
                batch_id="batch-base-system", params={"__managed_suite_kind": "base_system"},
                remote_work_dir="/tmp/managed-suite", status="RUNNING", start_time=None,
            )
            db = Mock()
            db.get.return_value = SimpleNamespace(password="private-sudo-password")
            executor = Mock()
            executor.exec_simple.return_value = "1000"
            executor.exec_sudo.return_value = (0, "", "")
            with (
                patch.object(task_runner, "_ensure_task_not_canceled"),
                patch.object(task_runner, "_set_status"),
                patch.object(task_runner, "_add_log") as add_log,
                patch.object(task_runner, "_monitor_detached_command") as monitor,
            ):
                task_runner._execute_command_task(db, executor, task, "task-one", _script_command(task))
            command = executor.exec_sudo.call_args.args[0]
            self.assertIn(f"bash ./{name}", command)
            self.assertIn("nohup setsid -f", command)
            self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "private-sudo-password")
            self.assertNotIn("private-sudo-password", command)
            self.assertNotIn("private-sudo-password", str(add_log.call_args_list))
            monitor.assert_called_once()

            executor.exec_sudo.return_value = (1, "", "Sorry, try again.")
            with (
                patch.object(task_runner, "_ensure_task_not_canceled"),
                patch.object(task_runner, "_set_status"),
                patch.object(task_runner, "_add_log"),
                patch.object(task_runner, "_monitor_detached_command") as monitor,
                self.assertRaises(task_runner.TaskRunnerError),
            ):
                task_runner._execute_command_task(db, executor, task, "task-one", _script_command(task))
            monitor.assert_not_called()

            executor.exec_simple.return_value = "0"
            executor.exec_sudo.reset_mock()
            with (
                patch.object(task_runner, "_ensure_task_not_canceled"),
                patch.object(task_runner, "_set_status"),
                patch.object(task_runner, "_add_log"),
                patch.object(task_runner, "_monitor_detached_command"),
            ):
                task_runner._execute_command_task(db, executor, task, "task-one", _script_command(task))
            executor.exec_sudo.assert_not_called()

    def test_single_script_and_other_managed_scripts_keep_unprivileged_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "lock_linux_release.sh").write_text("printf 'ran-as-ssh-user\\n'\n", encoding="utf-8")
            (directory / "other.sh").write_text("printf 'other-script\\n'\n", encoding="utf-8")
            for name, batch_id, params in (
                ("lock_linux_release.sh", None, {}),
                ("other.sh", "batch-other", {"__managed_suite_kind": "base_system"}),
            ):
                task = SimpleNamespace(
                    file_name=name, file_path=f"scripts/mpi/{name}",
                    batch_id=batch_id, params=params,
                )
                result = subprocess.run(
                    ["bash", "-c", _script_command(task)], cwd=directory,
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ran-as-ssh-user" if batch_id is None else "other-script", result.stdout)


if __name__ == "__main__":
    unittest.main()
