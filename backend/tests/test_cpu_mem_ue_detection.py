import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stress" / "cpu_mem_stress_report.sh"


class CpuMemoryUeDetectionTests(unittest.TestCase):
    def test_ue_patterns_are_explicit_and_fail_the_report(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("UE_ERROR_PATTERN=", source)
        self.assertIn("uecc", source.lower())
        self.assertIn("edac.*(ue|uncorrect)", source.lower())
        self.assertIn("uncorrected hardware memory error", source.lower())
        self.assertIn("UE_ERROR_COUNT=", source)
        self.assertIn("Uncorrectable ECC memory error detected (UE/UECC).", source)

    def test_kernel_monitor_uses_follow_new_and_excludes_generic_verification_text(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        critical_pattern = next(
            line for line in source.splitlines() if line.startswith("CRITICAL_ERR_PATTERN=")
        )
        self.assertIn("dmesg -W 2>/dev/null", source)
        self.assertNotIn("dmesg -w 2>/dev/null", source)
        self.assertNotIn("verification failed", critical_pattern)
        self.assertIn('journalctl -k --no-pager --since "$KERNEL_LOG_START_AT"', source)

    def test_reports_corrected_ecc_mce_separately_from_generic_events(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CORRECTED_ECC_MCE_PATTERN=", source)
        self.assertIn("Correctable ECC memory error detected", source)
        self.assertIn('EVENT_SHEET_NAME="CorrectedECC"', source)
        self.assertIn('cpu_mem_error_${TIME_TAG}.log', source)
        self.assertIn('echo "Hardware/System Event Details : ${ERR_LOG}"', source)
        self.assertNotIn('echo "Kernel Error : ${ERR_LOG}"', source)


if __name__ == "__main__":
    unittest.main()
