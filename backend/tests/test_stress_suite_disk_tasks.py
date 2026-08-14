from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.api.tasks import create_stress_suite
from app.core.task_runner import _resolve_task_remote_work_dir
from app.models.task import Task
from app.schemas.task import StressSuiteCreateRequest


class StressSuiteDiskTasksTests(unittest.TestCase):
    def test_preallocated_remote_directory_is_expanded_without_being_replaced(self) -> None:
        task = SimpleNamespace(
            remote_work_dir="~/hpcdeploy/tasks/stress/disk_stress-task-example",
            task_type="stress",
            file_name="disk_stress_report.sh",
        )

        self.assertEqual(
            _resolve_task_remote_work_dir(task, "/root"),
            "/root/hpcdeploy/tasks/stress/disk_stress-task-example",
        )

    @patch("app.api.tasks.write_audit_log")
    @patch("app.api.tasks._start_task_thread")
    @patch("app.api.tasks._get_library_file_or_400")
    def test_multiple_disk_directories_create_named_child_tasks(
        self,
        get_file: MagicMock,
        start_task: MagicMock,
        _audit: MagicMock,
    ) -> None:
        get_file.return_value = {"name": "disk_stress_report.sh"}
        server = SimpleNamespace(id=1, name="node01", status="online", tags=[])
        db = MagicMock()
        db.get.return_value = server
        db.query.return_value.filter.return_value.first.return_value = None

        result = create_stress_suite(
            StressSuiteCreateRequest(
                server_ids=[1],
                script_paths=["scripts/stress/disk_stress_report.sh"],
                params={"duration_seconds": 60, "disk_test_dirs": ["/", "/data"]},
            ),
            db,
        )

        tasks = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Task)]
        self.assertEqual([task.params["disk_test_dir"] for task in tasks], ["/", "/data"])
        self.assertEqual([task.depends_on_task_id for task in tasks], [None, None])
        self.assertEqual(len({task.remote_work_dir for task in tasks}), 2)
        self.assertEqual([item.task_name for item in result.items], ["磁盘压测 · /", "磁盘压测 · /data"])
        self.assertEqual(start_task.call_count, 0)

    @patch("app.api.tasks.write_audit_log")
    @patch("app.api.tasks._get_library_file_or_400")
    def test_each_server_creates_disk_children_only_for_its_own_selected_directories(
        self,
        get_file: MagicMock,
        _audit: MagicMock,
    ) -> None:
        get_file.return_value = {"name": "disk_stress_report.sh"}
        servers = {
            1: SimpleNamespace(id=1, name="node01", status="online", tags=[]),
            2: SimpleNamespace(id=2, name="node02", status="online", tags=[]),
        }
        db = MagicMock()
        db.get.side_effect = lambda _model, server_id: servers.get(server_id)
        db.query.return_value.filter.return_value.first.return_value = None

        create_stress_suite(
            StressSuiteCreateRequest(
                server_ids=[1, 2],
                script_paths=["scripts/stress/disk_stress_report.sh"],
                params={"duration_seconds": 60},
                disk_test_dirs_by_server={1: ["/", "/data"], 2: ["/", "/data1", "/data2"]},
            ),
            db,
        )

        tasks = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Task)]
        directories_by_server: dict[int, list[str]] = {}
        for task in tasks:
            directories_by_server.setdefault(task.server_id, []).append(task.params["disk_test_dir"])
        self.assertEqual(directories_by_server, {1: ["/", "/data"], 2: ["/", "/data1", "/data2"]})

    @patch("app.api.tasks.write_audit_log")
    @patch("app.api.tasks._get_library_file_or_400")
    def test_disk_children_share_the_cpu_predecessor_in_a_full_stress_suite(
        self,
        get_file: MagicMock,
        _audit: MagicMock,
    ) -> None:
        get_file.side_effect = lambda path: {"name": path.rsplit("/", 1)[-1]}
        server = SimpleNamespace(id=1, name="node01", status="online", tags=[])
        db = MagicMock()
        db.get.return_value = server
        db.query.return_value.filter.return_value.first.return_value = None

        create_stress_suite(
            StressSuiteCreateRequest(
                server_ids=[1],
                script_paths=[
                    "scripts/stress/gpu_stress_report.sh",
                    "scripts/stress/cpu_mem_stress_report.sh",
                    "scripts/stress/disk_stress_report.sh",
                ],
                params={"duration_seconds": 60, "disk_test_dirs": ["/", "/data"]},
            ),
            db,
        )

        tasks = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Task)]
        self.assertEqual([task.file_name for task in tasks], [
            "gpu_stress_report.sh", "cpu_mem_stress_report.sh", "disk_stress_report.sh", "disk_stress_report.sh",
        ])
        self.assertEqual(tasks[1].depends_on_task_id, tasks[0].task_id)
        self.assertEqual(tasks[2].depends_on_task_id, tasks[1].task_id)
        self.assertEqual(tasks[3].depends_on_task_id, tasks[1].task_id)


if __name__ == "__main__":
    unittest.main()
