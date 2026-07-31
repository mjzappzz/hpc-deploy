import unittest

from app.core.report_summary import resolve_failure_reason


class ReportSummaryFailureReasonTests(unittest.TestCase):
    def test_platform_marker_mismatch_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "stress_startup_marker_mismatch",
            "conclusion": "GPU 压测已实际启动，但旧版脚本缺少启动阶段标记，平台误判并终止任务。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress failed before start: dependency installation did not finish within 300s",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )

    def test_other_failures_keep_original_task_error(self) -> None:
        self.assertEqual(
            resolve_failure_reason(
                "SSH connection timed out",
                "UNKNOWN",
                {"category": "ssh_connection_failed", "conclusion": "任务无法连接到目标服务器。"},
            ),
            "SSH connection timed out",
        )


if __name__ == "__main__":
    unittest.main()
