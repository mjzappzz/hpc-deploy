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
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_task_search_matches_server_name_and_host(self) -> None:
        by_name = list_tasks(db=self.session, task_status=None, task_type=None, server_id=None, keyword="张艺", limit=50, offset=0, order="created_desc")
        by_host = list_tasks(db=self.session, task_status=None, task_type=None, server_id=None, keyword="10.87.141.88", limit=50, offset=0, order="created_desc")

        self.assertEqual([item.task_id for item in by_name.items], ["task-zhangyi"])
        self.assertEqual([item.task_id for item in by_host.items], ["task-zhangyi"])

    def test_batch_search_matches_server_name_host_and_script_name(self) -> None:
        by_name = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="张艺")
        by_host = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="10.87.141.88")
        by_script = list_batches(db=self.session, page=1, page_size=20, status=None, keyword="gpu_stress")

        self.assertEqual([item.batch_id for item in by_name.items], ["batch-zhangyi"])
        self.assertEqual([item.batch_id for item in by_host.items], ["batch-zhangyi"])
        self.assertEqual([item.batch_id for item in by_script.items], ["batch-zhangyi"])
