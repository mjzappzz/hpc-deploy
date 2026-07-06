import inspect
import unittest

from app.api import tasks
from app.core.report_summary import backfill_missing_report_summaries, unknown_report_summary


class CachedDiagnosisEndpointTests(unittest.TestCase):
    def test_diagnosis_endpoint_does_not_do_runtime_report_work(self) -> None:
        source = inspect.getsource(tasks.diagnose_task)

        self.assertNotIn("ARTIFACTS_DIR", source)
        self.assertNotIn("TaskLog", source)
        self.assertNotIn("diagnose_task_failure", source)
        self.assertNotIn("read_text", source)
        self.assertNotIn("iterdir", source)

    def test_unknown_report_summary_is_lightweight_fallback(self) -> None:
        task = type("TaskLike", (), {"task_id": "task-1"})()

        summary = unknown_report_summary(task)

        self.assertEqual(summary["report_status"], "UNKNOWN")
        self.assertEqual(summary["diagnosis"]["category"], "report_not_ready")
        self.assertNotIn("缺失", summary["diagnosis"]["conclusion"])
        self.assertEqual(summary["diagnosis"]["evidence"], [])

    def test_backfill_function_is_background_safe_entrypoint(self) -> None:
        self.assertTrue(callable(backfill_missing_report_summaries))


if __name__ == "__main__":
    unittest.main()
