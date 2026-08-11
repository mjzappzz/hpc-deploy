import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_COMMAND_VIEW = PROJECT_ROOT / "frontend/src/views/OpsCommands.vue"


class OpsCommandRichEditorTests(unittest.TestCase):
    def test_editor_exposes_a_bold_action_and_plain_text_paste(self) -> None:
        view = OPS_COMMAND_VIEW.read_text(encoding="utf-8")

        self.assertIn("加粗", view)
        self.assertIn("toggleBold", view)
        self.assertIn("handlePlainTextPaste", view)
        self.assertIn("v-html", view)

    def test_command_list_uses_title_label_and_exposes_pin_action(self) -> None:
        view = OPS_COMMAND_VIEW.read_text(encoding="utf-8")

        self.assertIn("<span>命令标题</span>", view)
        self.assertNotIn("<span>命令列表</span>", view)
        self.assertIn("toggleCommandStar", view)
        self.assertIn("hpcdeploy.starred-ops-command-ids", view)
        self.assertIn("StarFilled", view)
        self.assertIn("<Star v-else />", view)
        self.assertIn("is-starred", view)
        self.assertIn("var(--el-color-warning-light-9)", view)
        self.assertNotIn("requireAdminConfirm(actionLabel)", view)


if __name__ == "__main__":
    unittest.main()
