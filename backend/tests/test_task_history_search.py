import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.tasks import list_batches, list_tasks
from app.db.database import Base
from app.models.server import Server
from app.models.task import Task


class TaskHistorySearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        server = Server(name="张艺", host="10.87.141.88", username="root")
        self.session.add(server)
        self.session.flush()
        context_server = Server(name="批次上下文服务器", host="10.87.141.89", username="root")
        self.session.add(context_server)
        self.session.flush()
        self.session.add(
            Task(
                task_id="task-zhangyi",
                batch_id="batch-zhangyi",
                server_id=server.id,
                task_type="stress",
                file_path="stress/gpu_stress_report.sh",
                file_name="gpu_stress_report.sh",
                status="SUCCESS",
            )
        )
        self.session.add_all(
            [
                Task(
                    task_id="task-batch-running",
                    batch_id="batch-running-context",
                    server_id=context_server.id,
                    task_type="stress",
                    file_path="stress/context_gpu.sh",
                    file_name="context_gpu.sh",
                    status="RUNNING",
                    sequence_index=1,
                ),
                Task(
                    task_id="task-batch-success",
                    batch_id="batch-running-context",
                    server_id=context_server.id,
                    task_type="stress",
                    file_path="stress/cpu_memory_stress.sh",
                    file_name="cpu_memory_stress.sh",
                    status="SUCCESS",
                    sequence_index=2,
                ),
                Task(
                    task_id="task-batch-pending",
                    batch_id="batch-running-context",
                    server_id=context_server.id,
                    task_type="stress",
                    file_path="stress/disk_stress.sh",
                    file_name="disk_stress.sh",
                    status="PENDING",
                    sequence_index=3,
                ),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_task_search_matches_server_name_and_host(self) -> None:
        by_name = list_tasks(db=self.session, task_status=None, task_type=None, task_scope=None, server_id=None, keyword="张艺", limit=50, offset=0, order="created_desc")
        by_host = list_tasks(db=self.session, task_status=None, task_type=None, task_scope=None, server_id=None, keyword="10.87.141.88", limit=50, offset=0, order="created_desc")

        self.assertEqual([item.task_id for item in by_name.items], ["task-zhangyi"])
        self.assertEqual([item.task_id for item in by_host.items], ["task-zhangyi"])
        self.assertEqual(by_name.items[0].server_username, "root")

    def test_batch_search_matches_server_name_host_and_script_name(self) -> None:
        by_name = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="张艺")
        by_host = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="10.87.141.88")
        by_script = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="gpu_stress")

        self.assertEqual([item.batch_id for item in by_name.items], ["batch-zhangyi"])
        self.assertEqual([item.batch_id for item in by_host.items], ["batch-zhangyi"])
        self.assertEqual([item.batch_id for item in by_script.items], ["batch-zhangyi"])

    def test_running_filter_can_include_all_tasks_in_matching_batches(self) -> None:
        running_only = list_tasks(
            db=self.session,
            task_status="RUNNING",
            task_type=None,
            task_scope=None,
            server_id=None,
            keyword=None,
            limit=50,
            offset=0,
            order="created_desc",
        )
        with_batch_context = list_tasks(
            db=self.session,
            task_status="RUNNING",
            task_type=None,
            task_scope=None,
            server_id=None,
            keyword=None,
            limit=50,
            offset=0,
            order="created_desc",
            include_batch_context=True,
        )
        success_with_batch_context = list_tasks(
            db=self.session,
            task_status="SUCCESS",
            task_type=None,
            task_scope=None,
            server_id=None,
            keyword=None,
            limit=50,
            offset=0,
            order="created_desc",
            include_batch_context=True,
        )

        self.assertEqual([item.task_id for item in running_only.items], ["task-batch-running"])
        self.assertEqual(
            {item.task_id for item in with_batch_context.items},
            {"task-batch-running", "task-batch-success", "task-batch-pending"},
        )
        self.assertEqual(
            {item.task_id for item in success_with_batch_context.items},
            {"task-zhangyi", "task-batch-running", "task-batch-success", "task-batch-pending"},
        )

    def test_active_only_filter_excludes_pending_tasks(self) -> None:
        active = list_tasks(
            db=self.session,
            task_status=None,
            task_type=None,
            task_scope=None,
            server_id=None,
            keyword=None,
            limit=50,
            offset=0,
            order="created_desc",
            active_only=True,
        )

        self.assertEqual(
            {item.task_id for item in active.items},
            {"task-batch-running"},
        )
