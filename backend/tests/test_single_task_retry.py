from types import SimpleNamespace
import unittest

from app.api.tasks import _single_task_can_retry


class SingleTaskRetryTests(unittest.TestCase):
    def test_failed_or_report_failed_single_task_can_retry(self) -> None:
        self.assertTrue(_single_task_can_retry(SimpleNamespace(status="FAILED", batch_id=None)))
        self.assertTrue(_single_task_can_retry(SimpleNamespace(status="SUCCESS", batch_id=None, report_status="FAIL")))

    def test_batch_or_successful_single_task_cannot_use_single_retry(self) -> None:
        self.assertFalse(_single_task_can_retry(SimpleNamespace(status="FAILED", batch_id="batch-1")))
        self.assertFalse(_single_task_can_retry(SimpleNamespace(status="SUCCESS", batch_id=None, report_status="PASS")))


if __name__ == "__main__":
    unittest.main()
