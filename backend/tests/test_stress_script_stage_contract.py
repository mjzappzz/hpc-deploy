import unittest
from pathlib import Path


STRESS_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "stress"
STRESS_SCRIPTS = (
    "gpu_stress_report.sh",
    "cpu_mem_stress_report.sh",
    "disk_stress_report.sh",
)


class StressScriptStageContractTests(unittest.TestCase):
    def test_all_stress_scripts_emit_startup_stage_markers_in_order(self) -> None:
        for script_name in STRESS_SCRIPTS:
            with self.subTest(script=script_name):
                source = (STRESS_SCRIPTS_DIR / script_name).read_text(encoding="utf-8")

                dependency_start = source.index('echo "[STAGE] dependency_check_start"')
                dependency_done = source.index('echo "[STAGE] dependency_check_done"')
                stress_start = source.index('echo "[STAGE] stress_start"')

                self.assertLess(dependency_start, dependency_done)
                self.assertLess(dependency_done, stress_start)


if __name__ == "__main__":
    unittest.main()
