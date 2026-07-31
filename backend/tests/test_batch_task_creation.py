import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from fastapi import BackgroundTasks

from app.api.tasks import batch_run_task
from app.schemas.task import BatchTaskCreateRequest


class BatchTaskCreationTests(unittest.TestCase):
    @patch("app.api.tasks.write_audit_log")
    @patch("app.api.tasks._start_task_thread")
    @patch("app.api.tasks._create_task_for_server")
    @patch("app.api.tasks._get_library_file_or_400")
    def test_same_script_is_created_and_started_for_each_server(
        self,
        get_file: MagicMock,
        create_task: MagicMock,
        start_task: MagicMock,
        _write_audit: MagicMock,
    ) -> None:
        get_file.return_value = {
            "physical_category": "mpi",
            "name": "install_oneapi_2022.sh",
        }
        create_task.side_effect = ["task-server-1", "task-server-2"]

        servers = {
            1: SimpleNamespace(id=1, name="测试246", status="online"),
            2: SimpleNamespace(id=2, name="aliyun", status="online"),
        }
        db = MagicMock()
        db.get.side_effect = lambda _model, server_id: servers.get(server_id)
        db.query.return_value.filter.return_value.first.return_value = None

        response = batch_run_task(
            BatchTaskCreateRequest(
                server_ids=[1, 2],
                script_type="script",
                script_path="scripts/mpi/install_oneapi_2022.sh",
            ),
            BackgroundTasks(),
            db,
        )

        self.assertEqual(response.created, 2)
        self.assertEqual(response.script_name, "install_oneapi_2022.sh")
        self.assertEqual(response.batch_id, "")
        self.assertEqual(response.batch_ids, [])
        self.assertEqual(response.batches, [])
        self.assertEqual(response.task_ids, ["task-server-1", "task-server-2"])
        self.assertEqual([item.batch_id for item in response.items], ["", ""])
        self.assertEqual(
            [item.task_id for item in response.items],
            ["task-server-1", "task-server-2"],
        )
        self.assertEqual(
            [args.kwargs["batch_id"] for args in create_task.call_args_list],
            [None, None],
        )
        self.assertEqual(
            [args.args[4] for args in create_task.call_args_list],
            ["install_oneapi_2022.sh", "install_oneapi_2022.sh"],
        )
        start_task.assert_has_calls([call("task-server-1"), call("task-server-2")])


if __name__ == "__main__":
    unittest.main()
