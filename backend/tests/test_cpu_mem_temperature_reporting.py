import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stress" / "cpu_mem_stress_report.sh"


class CpuMemoryTemperatureReportingTests(unittest.TestCase):
    def test_cpu_temperature_collection_is_cross_vendor_and_reported(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("sensors -j", source)
        self.assertIn("Package id", source)
        self.assertIn("Tctl", source)
        self.assertIn("Tdie", source)
        self.assertIn('"coretemp", "k10temp", "zenpower", "cpu_thermal"', source)
        self.assertNotIn('ERROR: sensors not found', source)
        self.assertIn("cpu_temp_max_C", source)
        self.assertIn("CPU温度平均", source)
        self.assertIn("CPU温度最高", source)
        self.assertEqual(source.count('add_chart("CPU Temperature(°C)", 11, "J93")'), 2)


if __name__ == "__main__":
    unittest.main()
