import unittest
from unittest.mock import patch

from app.api.tasks import _parse_gpu


class _FakeExecutor:
    pass


class TaskGpuMonitorTests(unittest.TestCase):
    def test_parse_gpu_exposes_nvidia_smi_operational_metrics(self) -> None:
        responses = iter((
            "/usr/bin/nvidia-smi\nOK\n",
            "0, NVIDIA GeForce RTX 4090, 100, 20133, 23028, 82, 90, 419.25, 450.00, P2, 00000000:98:00.0\n",
        ))

        with patch("app.api.tasks._exec_monitor_cmd", side_effect=lambda *_args: next(responses)):
            result = _parse_gpu(_FakeExecutor())

        self.assertTrue(result["available"])
        self.assertEqual(result["items"], [{
            "index": "0",
            "name": "NVIDIA GeForce RTX 4090",
            "utilization_gpu": "100",
            "memory_used": "20133",
            "memory_total": "23028",
            "temperature": "82",
            "fan_speed": "90",
            "power_draw": "419.25",
            "power_limit": "450.00",
            "performance_state": "P2",
            "bus_id": "00000000:98:00.0",
        }])


if __name__ == "__main__":
    unittest.main()
