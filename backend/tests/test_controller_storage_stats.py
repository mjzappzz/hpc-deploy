import tempfile
import unittest
from pathlib import Path

from app.core.storage_stats import collect_directory_size, collect_storage_breakdown


class ControllerStorageStatsTests(unittest.TestCase):
    def test_collect_directory_size_reports_files_and_skips_symlinked_directories(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "nested").mkdir()
            (root / "nested" / "result.bin").write_bytes(b"12345")
            (root / "readme.txt").write_bytes(b"12")
            (root / "nested-link").symlink_to(root / "nested", target_is_directory=True)

            self.assertEqual(collect_directory_size(root), 7)

    def test_breakdown_keeps_known_categories_non_overlapping(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            data = root / "backend" / "data"
            artifacts = data / "artifacts"
            backups = data / "backups"
            gpu_library = data / "gpu_driver_library"
            artifacts.mkdir(parents=True)
            backups.mkdir()
            gpu_library.mkdir()
            (artifacts / "result.bin").write_bytes(b"a" * 11)
            (backups / "backup.db").write_bytes(b"b" * 13)
            (gpu_library / "libcuda.so").write_bytes(b"c" * 17)
            (data / "hpc_control_panel.db").write_bytes(b"d" * 19)
            (data / "other.log").write_bytes(b"e" * 23)
            (root / "runtime.log").write_bytes(b"f" * 29)

            breakdown = collect_storage_breakdown(
                project_root=root,
                database_path=data / "hpc_control_panel.db",
                artifacts_path=artifacts,
                backups_path=backups,
                gpu_library_path=gpu_library,
            )
            sizes = {item.key: item.size_bytes for item in breakdown}

            self.assertEqual(sizes["artifacts"], 11)
            self.assertEqual(sizes["sqlite_database"], 19)
            self.assertEqual(sizes["sqlite_backups"], 13)
            self.assertEqual(sizes["gpu_driver_library"], 17)
            self.assertEqual(sizes["controller_data_other"], 23)
            self.assertEqual(sizes["project_runtime"], 29)

    def test_missing_known_path_is_explicitly_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            data = root / "backend" / "data"
            data.mkdir(parents=True)
            items = collect_storage_breakdown(
                project_root=root,
                database_path=data / "missing.db",
                artifacts_path=data / "artifacts",
                backups_path=data / "backups",
                gpu_library_path=data / "gpu_driver_library",
            )

            self.assertEqual({item.key for item in items if item.status == "unavailable"}, {
                "artifacts", "sqlite_database", "sqlite_backups", "gpu_driver_library",
            })


if __name__ == "__main__":
    unittest.main()
