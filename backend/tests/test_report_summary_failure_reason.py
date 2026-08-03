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

    def test_interrupted_stress_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "stress_interrupted_before_report",
            "conclusion": "压测已进入实际负载后异常中断，疑似服务器重启或异常中断。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress script exited before report generation, no report found",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )

    def test_uncorrected_memory_error_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "uncorrected_memory_hardware_error",
            "conclusion": "内核日志已检测到不可纠正内存硬件错误。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress script exited before report generation, no report found",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )


if __name__ == "__main__":
    unittest.main()
