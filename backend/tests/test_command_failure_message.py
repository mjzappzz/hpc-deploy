import unittest

from app.core.task_runner import _select_command_failure_message


class CommandFailureMessageTests(unittest.TestCase):
    def test_prefers_script_error_marker_over_exit_code(self) -> None:
        messages = [
            ("SYSTEM", "executing command: bash ./lock_linux_release.sh"),
            ("INFO", "[ERROR] 仅允许在已安装 Rocky Linux 9.4 的服务器执行，当前版本：9.8"),
            ("SYSTEM", "command exited with code 1"),
        ]

        result = _select_command_failure_message(messages, 1)

        self.assertEqual(
            result,
            "仅允许在已安装 Rocky Linux 9.4 的服务器执行，当前版本：9.8",
        )

    def test_falls_back_when_script_has_no_specific_error(self) -> None:
        messages = [("INFO", "starting"), ("SYSTEM", "command exited with code 7")]

        self.assertEqual(
            _select_command_failure_message(messages, 7),
            "command exited with code 7",
        )


if __name__ == "__main__":
    unittest.main()
