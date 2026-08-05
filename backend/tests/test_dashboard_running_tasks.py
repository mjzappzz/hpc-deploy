import unittest
from pathlib import Path


class DashboardRunningTasksTests(unittest.TestCase):
    def test_summary_returns_all_active_tasks_without_recent_task_limit(self) -> None:
        source = (Path(__file__).parents[1] / "app" / "api" / "dashboard.py").read_text()

        self.assertIn("Task.status.in_(ACTIVE_TASK_STATUSES)", source)
        self.assertNotIn("order_by(Task.id.desc()).limit(10)", source)


if __name__ == "__main__":
    unittest.main()
