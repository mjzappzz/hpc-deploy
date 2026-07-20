import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stress" / "gpu_stress_report.sh"


class GpuBurnLogCompactionTests(unittest.TestCase):
    def test_normalizes_carriage_return_progress_before_sampling(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("tr '\\r' '\\n' < \"$BURN_RAW_LOG\" | awk", source)
        self.assertNotIn("' \"$BURN_RAW_LOG\"\n        echo \"[SUMMARY]", source)

        raw = (
            "0.0% first\r0.1% duplicate\r9.9% duplicate\r"
            "10.0% second bucket\r20.0% third bucket\rCUDA error: retained\n"
        )
        result = subprocess.run(
            [
                "bash",
                "-c",
                r'''tr '\r' '\n' | awk '
                    /^[[:space:]]*[0-9]+(\.[0-9]+)?%/ {
                        pct = $1; sub(/%$/, "", pct); bucket = int(pct / 10)
                        if (!(bucket in seen)) { print "[PROGRESS SAMPLE] " $0; seen[bucket] = 1 }
                        next
                    }
                    tolower($0) ~ /cuda error/ { print "[ERROR] " $0 }
                ' ''',
            ],
            input=raw,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            [
                "[PROGRESS SAMPLE] 0.0% first",
                "[PROGRESS SAMPLE] 10.0% second bucket",
                "[PROGRESS SAMPLE] 20.0% third bucket",
                "[ERROR] CUDA error: retained",
            ],
        )


if __name__ == "__main__":
    unittest.main()
