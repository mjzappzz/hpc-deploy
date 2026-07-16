from types import SimpleNamespace
import unittest

from app.api.tasks import _fail_suite_task_records_for_scheduler, _wait_for_active_suite_task


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


class StressSuiteSchedulerTests(unittest.TestCase):
    def test_scheduler_failure_marks_unfinished_tasks_failed(self) -> None:
        db = FakeDb()
        tasks = [
            SimpleNamespace(task_id="task-1", status="PENDING", end_time=None, error_message=None),
            SimpleNamespace(task_id="task-2", status="RUNNING", end_time=None, error_message=None),
            SimpleNamespace(task_id="task-3", status="SUCCESS", end_time=None, error_message=None),
        ]

        failed = _fail_suite_task_records_for_scheduler(db, tasks, "scheduler blocked")

        self.assertEqual(failed, 2)
        self.assertEqual(tasks[0].status, "FAILED")
        self.assertEqual(tasks[1].status, "FAILED")
        self.assertEqual(tasks[2].status, "SUCCESS")
        self.assertEqual(tasks[0].error_message, "scheduler blocked")
        self.assertEqual(len(db.added), 2)
        self.assertEqual(db.commits, 1)

    def test_recovery_worker_waits_for_active_predecessor_to_finish(self) -> None:
        task = SimpleNamespace(status="RUNNING")

        class RefreshDb:
            def refresh(self, _task) -> None:
                pass

        def finish_task(_seconds: float) -> None:
            task.status = "SUCCESS"

        with unittest.mock.patch("app.api.tasks.sleep", side_effect=finish_task):
            completed = _wait_for_active_suite_task(RefreshDb(), task)

        self.assertTrue(completed)
        self.assertEqual(task.status, "SUCCESS")


if __name__ == "__main__":
    unittest.main()
