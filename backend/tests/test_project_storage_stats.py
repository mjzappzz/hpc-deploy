import tempfile
import unittest
from pathlib import Path

from app.core.project_storage import collect_project_storage


class ProjectStorageStatsTests(unittest.TestCase):
    def test_project_total_uses_only_local_modules_and_keeps_other_files_separate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            workspace = Path(raw_root)
            root = workspace / "project"
            root.mkdir()
            data = root / "backend" / "data"
            artifacts = data / "artifacts"
            artifacts.mkdir(parents=True)
            (artifacts / "report.txt").write_bytes(b"a" * 10)
            (workspace / "outside-project.bin").write_bytes(b"x" * 100)
            (root / "runtime.log").write_bytes(b"r" * 5)

            result = collect_project_storage(
                project_root=root,
                modules=[("artifacts", "任务产物", artifacts), ("database", "SQLite 数据库", data / "db.sqlite")],
            )

            sizes = {item.key: item.size_bytes for item in result.items}
            self.assertEqual(sizes["artifacts"], 10)
            self.assertEqual(sizes["database"], 0)
            self.assertEqual(sizes["other_project_runtime"], 5)
            self.assertEqual(result.project_total_bytes, 15)
            self.assertEqual(result.project_total_file_count, 2)

    def test_missing_module_is_not_counted_as_zero_without_status(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = collect_project_storage(
                project_root=root,
                modules=[("missing", "缺失模块", root / "missing")],
            )

            missing = next(item for item in result.items if item.key == "missing")
            self.assertEqual(missing.status, "unavailable")
            self.assertIsNone(missing.percentage)


if __name__ == "__main__":
    unittest.main()
