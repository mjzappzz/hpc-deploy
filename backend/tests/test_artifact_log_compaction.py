import tempfile
import unittest
from pathlib import Path

from app.core.artifact_collector import _compact_log_file


class ArtifactLogCompactionTests(unittest.TestCase):
    def test_compacts_download_progress_and_keeps_stage_and_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "task.log"
            path.write_text(
                "[INFO] download started\n"
                "   500K .......... .......... .......... .......... ..........  0% 53.6M 77s\n"
                "  1000K .......... .......... .......... .......... ..........  0% 44.2M 55s\n"
                "[ERROR] download failed\n",
                encoding="utf-8",
            )

            changed = _compact_log_file(path)
            compacted = path.read_text(encoding="utf-8")

        self.assertTrue(changed)
        self.assertIn("[INFO] download started", compacted)
        self.assertIn("[ERROR] download failed", compacted)
        self.assertNotIn("500K ..........", compacted)
        self.assertIn("已省略", compacted)


if __name__ == "__main__":
    unittest.main()
