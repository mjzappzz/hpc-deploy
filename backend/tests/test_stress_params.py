import unittest

from fastapi import HTTPException

from app.core.stress_params import validate_stress_params, validate_stress_suite_params


class StressIntervalValidationTests(unittest.TestCase):
    def test_single_stress_accepts_custom_interval(self) -> None:
        result = validate_stress_params(
            {"duration_seconds": 600, "interval_seconds": 17},
            "cpu_mem_stress_report.sh",
        )
        self.assertEqual(result["interval_seconds"], 17)

    def test_suite_accepts_custom_interval(self) -> None:
        result = validate_stress_suite_params(
            {"duration_seconds": 600, "interval_seconds": 17},
            has_disk=False,
        )
        self.assertEqual(result["interval_seconds"], 17)

    def test_suite_accepts_multiple_disk_test_directories(self) -> None:
        result = validate_stress_suite_params(
            {"duration_seconds": 60, "disk_test_dirs": ["/", "/data"]},
            has_disk=True,
        )

        self.assertEqual(result["disk_test_dirs"], ["/", "/data"])

    def test_interval_cannot_exceed_duration(self) -> None:
        with self.assertRaises(HTTPException):
            validate_stress_params(
                {"duration_seconds": 60, "interval_seconds": 61},
                "gpu_stress_report.sh",
            )

    def test_gpu_precision_accepts_fp64(self) -> None:
        result = validate_stress_params(
            {"duration_seconds": 60, "gpu_precision": "fp64"},
            "gpu_stress_report.sh",
        )
        self.assertEqual(result["gpu_precision"], "fp64")

    def test_gpu_precision_rejects_unknown_value(self) -> None:
        with self.assertRaises(HTTPException):
            validate_stress_params(
                {"duration_seconds": 60, "gpu_precision": "tensor"},
                "gpu_stress_report.sh",
            )


if __name__ == "__main__":
    unittest.main()
