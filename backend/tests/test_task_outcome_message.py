import unittest

from app.core.task_serializer import normalize_success_skip_message


class TaskOutcomeMessageTests(unittest.TestCase):
    def test_normalizes_supported_whole_task_skip_messages(self) -> None:
        self.assertEqual(
            normalize_success_skip_message("[INFO] 当前系统版本为 Rocky Linux 9.8，非 9.4，无需锁定系统版本"),
            "当前系统版本为 Rocky Linux 9.8，非 9.4，无需锁定系统版本",
        )
        self.assertEqual(
            normalize_success_skip_message("nvidia-smi is available; skipping NVIDIA driver installation"),
            "检测到 nvidia-smi 可用，已跳过 NVIDIA 驱动安装",
        )
        self.assertEqual(
            normalize_success_skip_message("CUDA Toolkit 12.8 is already installed; skipping"),
            "CUDA Toolkit 12.8 已安装，已跳过安装",
        )

    def test_ignores_partial_step_skip_messages(self) -> None:
        self.assertIsNone(normalize_success_skip_message("Dependencies already installed, skip install."))
        self.assertIsNone(normalize_success_skip_message("Nouveau is not loaded; skipping disable/reboot and continuing installation"))


if __name__ == "__main__":
    unittest.main()
