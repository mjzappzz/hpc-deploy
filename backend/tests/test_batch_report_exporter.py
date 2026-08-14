from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from app.core.batch_report_exporter import build_batch_report_zip


class BatchReportExporterTests(unittest.TestCase):
    def test_batch_zip_preserves_every_disk_report_original_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifacts_dir = Path(directory)
            root_report = "disk_stress_report_2026-08-14_112000_root.xlsx"
            data_report = "disk_stress_report_2026-08-14_112000_data.xlsx"
            for task_id, report_name in (("task-root", root_report), ("task-data", data_report)):
                task_dir = artifacts_dir / task_id
                task_dir.mkdir()
                (task_dir / report_name).write_bytes(b"xlsx")

            tasks = [
                SimpleNamespace(
                    id=1, task_id="task-root", server_id=1, file_name="disk_stress_report.sh",
                    params={"disk_test_dir": "/"}, status="SUCCESS", sequence_index=3,
                    created_at=datetime(2026, 8, 14, 11, 20),
                ),
                SimpleNamespace(
                    id=2, task_id="task-data", server_id=1, file_name="disk_stress_report.sh",
                    params={"disk_test_dir": "/data"}, status="SUCCESS", sequence_index=4,
                    created_at=datetime(2026, 8, 14, 11, 20),
                ),
            ]
            server = SimpleNamespace(id=1, name="node01")

            with patch("app.core.batch_report_exporter.ARTIFACTS_DIR", artifacts_dir):
                exported = build_batch_report_zip("batch-example", tasks, {1: server})
            try:
                with zipfile.ZipFile(exported.path) as archive:
                    self.assertEqual(archive.namelist(), [root_report, data_report])
            finally:
                exported.path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
