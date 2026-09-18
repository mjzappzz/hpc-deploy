import unittest
from pathlib import Path


class DashboardRunningTasksTests(unittest.TestCase):
    def test_summary_returns_all_active_tasks_without_recent_task_limit(self) -> None:
        source = (Path(__file__).parents[1] / "app" / "api" / "dashboard.py").read_text()

        self.assertIn("Task.status.in_(ACTIVE_TASK_STATUSES)", source)
        self.assertNotIn("order_by(Task.id.desc()).limit(10)", source)

    def test_summary_keeps_the_fifty_most_recent_successful_or_failed_tasks(self) -> None:
        source = (Path(__file__).parents[1] / "app" / "api" / "dashboard.py").read_text()

        self.assertIn('COMPLETED_TASK_STATUSES = ("SUCCESS", "FAILED")', source)
        self.assertIn("Task.status.in_(COMPLETED_TASK_STATUSES)", source)
        self.assertIn(".order_by(Task.end_time.desc().nullslast(), Task.id.desc())", source)
        self.assertIn(".limit(50)", source)

    def test_summary_aggregates_complete_batches_with_history_status_logic(self) -> None:
        source = (Path(__file__).parents[1] / "app" / "api" / "dashboard.py").read_text()

        self.assertIn('BATCH_TERMINAL_TASK_STATUSES = ("SUCCESS", "FAILED", "CANCELED")', source)
        self.assertIn("from app.api.tasks import _compute_batch_status, _latest_batch_attempts", source)
        self.assertIn("Task.batch_id.in_(batch_ids)", source)
        self.assertIn("recent_completed_batches.append(RecentCompletedBatchItem(", source)
        self.assertIn("server_count=len(servers)", source)


if __name__ == "__main__":
    unittest.main()
