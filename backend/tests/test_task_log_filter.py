import unittest

from app.core.task_runner import _prepare_task_log_message


class TaskLogFilterTests(unittest.TestCase):
    def test_suppresses_carriage_return_progress_output(self) -> None:
        message = "10.0%  proc'd: 100 (50000 Gflop/s)\r10.1%  proc'd: 101 (50000 Gflop/s)"

        self.assertIsNone(_prepare_task_log_message("INFO", message))

    def test_suppresses_wget_progress_rows(self) -> None:
        message = "   500K .......... .......... .......... .......... ..........  0% 53.6M 77s"

        self.assertIsNone(_prepare_task_log_message("STDERR", message))

    def test_keeps_regular_info_message(self) -> None:
        self.assertEqual(_prepare_task_log_message("INFO", "report collected"), "report collected")

    def test_truncates_oversized_regular_message_by_utf8_bytes(self) -> None:
        result = _prepare_task_log_message("INFO", "中" * 2000)

        self.assertIsNotNone(result)
        self.assertLessEqual(len(result.encode("utf-8")), 4096)
        self.assertTrue(result.endswith("…[日志已截断]"))


if __name__ == "__main__":
    unittest.main()
