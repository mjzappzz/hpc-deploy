import unittest

from app.api.tasks import _parse_iostat


class TaskDiskMonitorTests(unittest.TestCase):
    def test_parse_iostat_uses_the_second_interval_and_exposes_io_metrics(self) -> None:
        output = """Linux 5.14 (host)\n\nDevice            r/s     rkB/s   w/s     wkB/s  aqu-sz  r_await  w_await  %util\nnvme0n1          1.00      4.00  2.00     8.00    0.01     0.10     0.20   1.00\n\nDevice            r/s     rkB/s   w/s     wkB/s  aqu-sz  r_await  w_await  %util\nnvme0n1        100.00  40960.00 200.00 81920.00    3.50     1.25     2.50  88.00\n"""

        self.assertEqual(_parse_iostat(output), [{
            "device": "nvme0n1",
            "read_iops": 100.0,
            "write_iops": 200.0,
            "read_bandwidth": 40960.0,
            "write_bandwidth": 81920.0,
            "bandwidth_unit": "kB/s",
            "read_await_ms": 1.25,
            "write_await_ms": 2.5,
            "queue_depth": 3.5,
            "utilization_percent": 88.0,
        }])


if __name__ == "__main__":
    unittest.main()
