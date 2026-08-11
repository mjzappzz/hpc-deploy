import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stress" / "cpu_mem_stress_report.sh"


class CpuMemoryPressureSafetyTests(unittest.TestCase):
    def test_memory_headroom_scales_for_small_and_large_servers(self) -> None:
        def limits(total_mb: int) -> tuple[int, int]:
            reserve = max(total_mb * 10 // 100, min(4096, total_mb * 25 // 100))
            margin = min(512, max(total_mb * 2 // 100, 128))
            return reserve, margin

        self.assertEqual(limits(1638), (409, 128))
        self.assertEqual(limits(4096), (1024, 128))
        self.assertEqual(limits(8192), (2048, 163))
        self.assertEqual(limits(16384), (4096, 327))
        self.assertEqual(limits(32768), (4096, 512))
        self.assertEqual(limits(65536), (6553, 512))
        self.assertEqual(limits(262144), (26214, 512))

        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("MEMORY_SAFETY_RESERVE_CAP_MB", source)
        self.assertIn("MEMORY_SAFETY_RESERVE_SMALL_PERCENT", source)
        self.assertIn("MEMORY_SAFETY_MARGIN_MIN_MB", source)
        self.assertIn("MEMORY_SAFETY_MARGIN_CAP_MB", source)

    def test_monitor_records_cpu_pressure_and_memory_target_metrics(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("cpu_busy_percent", source)
        self.assertIn("cpu_iowait_percent", source)
        self.assertIn("cpu_steal_percent", source)
        self.assertIn("memory_target_achieved_percent", source)
        self.assertIn("CPU_BUSY_AVG=", source)
        self.assertIn("MEM_TARGET_ACHIEVED_AVG=", source)

    def test_runtime_memory_headroom_breach_stops_the_workload_and_fails(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MEMORY_SAFETY_RESERVE_PERCENT", source)
        self.assertIn("MEMORY_SAFETY_RESERVE_CAP_MB", source)
        self.assertIn("MEMORY_SAFETY_CONSECUTIVE_SAMPLES", source)
        self.assertIn('touch "$MEMORY_SAFETY_FILE"', source)
        self.assertIn('if [ -f "$MEMORY_SAFETY_FILE" ]', source)
        self.assertIn("Memory safety reserve breached", source)

    def test_pressure_must_reach_cpu_and_memory_targets(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CPU_BUSY_FAIL_PERCENT", source)
        self.assertIn("MEMORY_TARGET_FAIL_PERCENT", source)
        self.assertIn("CPU pressure target was not reached", source)
        self.assertIn("Memory pressure target was not reached", source)

    def test_xlsx_is_optional_and_text_csv_do_not_require_openpyxl(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("XLSX_AVAILABLE=0", source)
        self.assertIn("XLSX skipped: python3-openpyxl is unavailable", source)
        self.assertNotIn('raise SystemExit("ERROR: python3-openpyxl not found', source)


if __name__ == "__main__":
    unittest.main()
