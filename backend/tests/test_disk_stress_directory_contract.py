import unittest
from types import SimpleNamespace
from pathlib import Path

from app.api.tasks import _build_command_preview
from app.core.task_runner import _build_stress_command
from app.core.stress_params import validate_stress_params


class DiskStressDirectoryContractTests(unittest.TestCase):
    def test_non_root_mount_uses_two_workers_by_default(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "stress" / "disk_stress_report.sh").read_text(encoding="utf-8")

        self.assertIn('if [ "$MOUNT_POINT" != "/" ] && [ -z "${WORKERS+x}" ]; then', source)
        self.assertIn('  HDD_WORKERS=2', source)
        self.assertIn('HDD_WORKERS=${WORKERS:-$DEFAULT_HDD_WORKERS}', source)
        self.assertIn('HDD_BYTES=20G', source)
        self.assertIn('  HDD_BYTES=1G', source)
        self.assertIn('--hdd-bytes ${HDD_BYTES}', source)

    def test_disk_test_directory_is_the_script_third_argument(self) -> None:
        params = {
            "duration_seconds": 60,
            "interval_seconds": 10,
            "disk_test_dir": "/data",
        }
        task = SimpleNamespace(file_name="disk_stress_report.sh", params=params)

        self.assertEqual(
            _build_stress_command(task),
            "./disk_stress_report.sh 60 10 '/data'",
        )
        self.assertEqual(
            _build_command_preview(
                task_type="stress",
                file_name="disk_stress_report.sh",
                params=params,
                remote_work_dir="/root/hpcdeploy/tasks/stress/example",
            ),
            "./disk_stress_report.sh 60 10 /data",
        )

    def test_root_mountpoint_is_a_valid_disk_test_target(self) -> None:
        params = validate_stress_params(
            {"duration_seconds": 60, "disk_test_dir": "/"},
            "disk_stress_report.sh",
        )

        self.assertEqual(params["disk_test_dir"], "/")


if __name__ == "__main__":
    unittest.main()
