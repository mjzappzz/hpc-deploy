import inspect
import unittest

from app.api import tasks


class TaskMonitorCapacityTests(unittest.TestCase):
    def test_monitor_lock_allows_one_sample_and_can_be_reused(self) -> None:
        task_id = "monitor-capacity-test"
        first_lock = tasks._try_acquire_task_monitor_lock(task_id)
        self.assertIsNotNone(first_lock)
        self.assertIsNone(tasks._try_acquire_task_monitor_lock(task_id))

        tasks._release_task_monitor_lock(task_id, first_lock)

        second_lock = tasks._try_acquire_task_monitor_lock(task_id)
        self.assertIsNotNone(second_lock)
        tasks._release_task_monitor_lock(task_id, second_lock)

    def test_structured_monitor_rejects_overlap_before_opening_ssh(self) -> None:
        source = inspect.getsource(tasks.task_monitor_structured)

        self.assertIn("_try_acquire_task_monitor_lock(task_id)", source)
        self.assertIn("status_code=status.HTTP_429_TOO_MANY_REQUESTS", source)

    def test_structured_monitor_releases_its_database_session_before_ssh(self) -> None:
        source = inspect.getsource(tasks.task_monitor_structured)

        self.assertLess(source.index("db.close()"), source.index("executor.connect("))


if __name__ == "__main__":
    unittest.main()
