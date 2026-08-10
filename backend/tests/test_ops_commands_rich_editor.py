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


if __name__ == "__main__":
    unittest.main()
