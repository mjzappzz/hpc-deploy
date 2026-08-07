import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stress" / "gpu_stress_report.sh"


class GpuBurnLogCompactionTests(unittest.TestCase):
    def test_report_distinguishes_driver_from_installed_cuda_toolkit(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("--query-gpu=driver_version", source)
        self.assertIn('"NVIDIA 驱动版本"', source)
        self.assertIn('"CUDA Toolkit 版本"', source)
        self.assertNotIn('"CUDA Version Driver"', source)
        self.assertNotIn('"CUDA Toolkit nvcc"', source)

    def test_streams_carriage_return_progress_without_retaining_a_raw_log(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("stream_gpu_burn_output", source)
        self.assertIn("tr '\\r' '\\n' | awk", source)
        self.assertNotIn("BURN_RAW_LOG", source)
        self.assertIn("CUDA_VISIBLE_DEVICES", source)
        self.assertIn("ensure_gpu_burn_cached_binary", source)
        self.assertIn("Start gpu-burn for GPU", source)

    def test_builds_and_verifies_a_gpu_matched_sm_fatbin(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("UNIVERSAL_GPU_ARCHES", source)
        self.assertNotIn("FORCE_REBUILD", source)
        self.assertNotIn('GPU_BURN="${GPU_BURN_DIR}/gpu_burn"', source)
        self.assertIn("only the physical GPUs on this server", source)
        self.assertIn("-gencode=arch=compute_", source)
        self.assertIn(",code=sm_", source)
        self.assertIn("make COMPUTE= NVCCFLAGS=", source)
        self.assertIn("cuobjdump --list-elf", source)
        self.assertIn("compare.fatbin is missing verified", source)
        self.assertIn("GPU_BURN_BUILD_LOCK", source)
        self.assertIn("flock -x 9", source)
        self.assertIn("Reuse verified GPU-matched fat binary", source)
        self.assertNotIn('ARCH_BUILD_ROOT="${WORKDIR}', source)
        self.assertNotIn('"$build_dir/gpu_burn"', source)

    def test_refreshes_gpu_burn_source_only_after_confirmed_kernel_mismatch(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("GPU_BURN_REPOSITORY=", source)
        self.assertIn("git clone --depth 1", source)
        self.assertIn("ensure_gpu_burn_source", source)
        self.assertIn("Local gpu-burn source is missing; restoring it from upstream", source)
        self.assertIn("Local gpu-burn source restored", source)
        self.assertIn("refresh_gpu_burn_source_after_kernel_mismatch", source)
        self.assertIn("Confirmed gpu-burn kernel-image mismatch", source)
        self.assertIn("fail fast", source)
        self.assertIn("stop_gpu_burn_process_tree", source)
        self.assertIn("pgrep -P", source)

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
