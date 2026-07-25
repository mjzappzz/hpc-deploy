import unittest

from app.core.task_runner import _prepare_task_log_message, _should_keep_progress_message


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

    def test_drops_repeated_integer_progress_for_same_task(self) -> None:
        previous = "[########################################          ]  81% (Elapsed: 35166s / 43260s)"
        current = "[########################################          ]  81% (Elapsed: 35286s / 43260s)"

        self.assertFalse(_should_keep_progress_message(current, previous))

    def test_keeps_progress_when_integer_percentage_changes(self) -> None:
        previous = "[#######################################           ]  80% (Elapsed: 34926s / 43260s)"
        current = "[########################################          ]  81% (Elapsed: 35166s / 43260s)"

        self.assertTrue(_should_keep_progress_message(current, previous))

    def test_keeps_non_progress_messages(self) -> None:
        self.assertTrue(_should_keep_progress_message("[STAGE] report_generation", "81%"))


if __name__ == "__main__":
    unittest.main()
