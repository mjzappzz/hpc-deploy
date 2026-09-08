from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import BackgroundTasks

from app.api import tasks
from app.core.cuda_toolkit_runner import CUDA_TOOLKIT_TASK_TYPE
from app.core.gpu_driver_runner import GPU_DRIVER_TASK_TYPE


class _FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1


class CudaToolkitRetryTests(unittest.TestCase):
    def test_retry_uses_cuda_runner_instead_of_library_file_validation(self) -> None:
        original = SimpleNamespace(
            task_id="task-original",
            server_id=7,
            batch_id=None,
            status="FAILED",
            task_type=CUDA_TOOLKIT_TASK_TYPE,
            file_path="cuda-toolkit/auto",
            file_name="cuda-toolkit-install.sh",
            params={"cuda_version": "12.8", "force_install": False, "os_profile": "ubuntu2404"},
            command_preview="old preview",
        )
        server = SimpleNamespace(id=7, name="cuda-host", os_info="Ubuntu 24.04.2 LTS")
        db = _FakeDb()
        background_tasks = BackgroundTasks()

        with (
            patch.object(tasks, "_get_task_or_404", return_value=original),
            patch.object(tasks, "_get_server_or_400", return_value=server),
            patch.object(tasks, "_generate_task_id", return_value="task-retry"),
            patch.object(tasks, "write_audit_log"),
            patch.object(tasks, "_get_library_file_or_400") as get_library_file,
        ):
            result = tasks.retry_single_task("task-original", background_tasks, db)

        self.assertEqual(result.retry_task_id, "task-retry")
        self.assertFalse(get_library_file.called)
        retry_task = next(task for task in db.added if getattr(task, "task_id", None) == "task-retry")
        self.assertEqual(retry_task.task_type, CUDA_TOOLKIT_TASK_TYPE)
        self.assertEqual(retry_task.params["cuda_version"], "12.8")
        self.assertEqual(retry_task.params["__retry_of_task_id"], "task-original")
        self.assertEqual(background_tasks.tasks[0].func, tasks.run_cuda_toolkit_task)

    def test_gpu_retry_preserves_kernel_maintenance_authorization(self) -> None:
        original = SimpleNamespace(
            task_id="task-original",
            server_id=7,
            batch_id=None,
            status="FAILED",
            task_type=GPU_DRIVER_TASK_TYPE,
            file_path="gpu-driver/auto",
            file_name="nvidia-linux-driver.run",
            params={
                "driver_type": "geforce",
                "driver_id": "a" * 24,
                "allow_kernel_maintenance": True,
            },
            command_preview="old preview",
        )
        server = SimpleNamespace(id=7, name="gpu-host", os_info="Rocky Linux 9.4")
        db = _FakeDb()
        background_tasks = BackgroundTasks()

        with (
            patch.object(tasks, "_get_task_or_404", return_value=original),
            patch.object(tasks, "_get_server_or_400", return_value=server),
            patch.object(tasks, "_generate_task_id", return_value="task-retry"),
            patch.object(tasks, "write_audit_log"),
            patch.object(tasks, "resolve_library_driver", return_value=object()),
        ):
            result = tasks.retry_single_task("task-original", background_tasks, db)

        self.assertEqual(result.retry_task_id, "task-retry")
        retry_task = next(task for task in db.added if getattr(task, "task_id", None) == "task-retry")
        self.assertTrue(retry_task.params["allow_kernel_maintenance"])
        self.assertEqual(background_tasks.tasks[0].func, tasks.run_rocky9_gpu_driver_task)


if __name__ == "__main__":
    unittest.main()
