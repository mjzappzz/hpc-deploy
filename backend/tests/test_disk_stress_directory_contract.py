import unittest
from types import SimpleNamespace
from pathlib import Path

from app.api.tasks import _build_command_preview
from app.core.task_runner import _build_stress_command
from app.core.stress_params import validate_stress_params


class DiskStressDirectoryContractTests(unittest.TestCase):
    def test_disk_profile_is_selected_from_the_backing_device_when_workers_are_not_overridden(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "stress" / "disk_stress_report.sh").read_text(encoding="utf-8")

        self.assertIn('resolve_backing_device', source)
        self.assertIn('lsblk -s -n -r -o NAME,TYPE', source)
        self.assertIn('ROTA', source)
        self.assertIn('TRAN', source)
        self.assertIn('select_disk_profile', source)
        self.assertIn('fit_auto_profile_to_capacity', source)
        self.assertIn('DISK_PROFILE=', source)
        self.assertIn('AUTO_PROFILE=1', source)
        self.assertIn('HDD_PROFILE_WORKERS=2', source)
        self.assertIn('HDD_PROFILE_BYTES=1G', source)
        self.assertIn('SSD_WORKERS=4', source)
        self.assertIn('NVME_WORKERS=8', source)
        self.assertIn('ensure_capacity_budget', source)
        self.assertIn('SAFETY_RESERVE_BYTES', source)
        self.assertIn('Available capacity is below the automatic disk stress safety budget', source)
        self.assertIn('Storage Profile', source)
        self.assertIn('Safety Reserve', source)
        self.assertIn('HDD_IO_OPTS="wr-rnd,direct,sync"', source)
        self.assertIn('--hdd-opts ${HDD_IO_OPTS}', source)
        self.assertIn('I/O Path', source)
        self.assertIn('--hdd-bytes ${HDD_BYTES}', source)
        self.assertIn('disk_stress_report_${TIME_TAG}_${REPORT_TARGET_SUFFIX}.xlsx', source)
        self.assertIn('REPORT_TARGET_SUFFIX="root"', source)

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
