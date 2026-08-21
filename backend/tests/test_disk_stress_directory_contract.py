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
        self.assertIn('FIO_RW="randrw"', source)
        self.assertIn('FIO_RWMIXWRITE=70', source)
        self.assertIn('FIO_BS="4k"', source)
        self.assertIn('FIO_PERFORMANCE_IOENGINE="libaio"', source)
        self.assertIn('FIO_DURABILITY_BYTES="8M"', source)
        self.assertIn('FIO_DURABILITY_BYTES="32M"', source)
        self.assertIn('FIO_DURABILITY_BYTES="256M"', source)
        self.assertIn('if [ "$DURATION" -le 180 ]; then', source)
        self.assertIn('elif [ "$DURATION" -le 3600 ]; then', source)
        self.assertIn('--name=hpcdeploy-performance', source)
        self.assertIn('--name=hpcdeploy-durability', source)
        self.assertIn('--iodepth="${FIO_PERFORMANCE_IODEPTH}"', source)
        self.assertIn('--fdatasync=1', source)
        self.assertIn('--rwmixwrite="${FIO_RWMIXWRITE}"', source)
        self.assertIn('--direct=1', source)
        self.assertIn('--fdatasync=1', source)
        self.assertIn('--verify="${FIO_VERIFY}"', source)
        self.assertIn('--clat_percentiles=1', source)
        self.assertIn('--percentile_list=95:99', source)
        self.assertIn('--output-format=json', source)
        self.assertIn('read_MBps,read_iops,read_await_ms,write_MBps,write_iops,write_await_ms,util_percent', source)
        self.assertNotIn('stress-ng \\\n    --hdd', source)
        self.assertNotIn('--filename_format=', source)
        self.assertIn('json_text[json_text.find("{"):]', source)
        self.assertIn('"FIO_METRICS_STATUS": "invalid_json"', source)
        self.assertIn('fio JSON result is missing or invalid.', source)
        self.assertIn('PERFORMANCE_DURATION=$DURATION', source)
        self.assertIn('FIO_PERFORMANCE_TOTAL_QD=$((HDD_WORKERS * FIO_PERFORMANCE_IODEPTH))', source)
        self.assertIn('fixed-size write and CRC32C verify', source)
        self.assertIn('--size="${HDD_BYTES}"', source)
        durability_start = source.index('--name=hpcdeploy-durability')
        durability_end = source.index('DURABILITY_RET=$?', durability_start)
        durability_command = source[durability_start:durability_end]
        self.assertIn('--do_verify=1', durability_command)
        self.assertNotIn('--time_based=1', durability_command)
        self.assertNotIn('--runtime=', durability_command)
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
