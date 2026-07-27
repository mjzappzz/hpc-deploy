import unittest

from app.core.ssh_detector import _summarize_cpu_info, _summarize_gpu_info


class SshDetectorTests(unittest.TestCase):
    def test_summarize_cpu_info_supports_localized_lscpu_output(self) -> None:
        raw = """架构： x86_64
CPU： 192
型号名称： AMD Ryzen Threadripper PRO 7995WX 96-Cores
"""

        self.assertEqual(
            _summarize_cpu_info(raw),
            "AMD Ryzen Threadripper PRO 7995WX 96-Cores / 192C",
        )

    def test_cuda_version_file_fallback_is_reported_without_nvcc(self) -> None:
        gpu_info, gpu_status = _summarize_gpu_info(
            """01:00.0 VGA compatible controller: NVIDIA Corporation AD102 [GeForce RTX 4090] (rev a1)
---GPU-SPLIT---
0, NVIDIA GeForce RTX 4090, 580.159.04, 24564, 12, 41, 0
---CUDA-SPLIT---
__NVCC_NOT_FOUND__
__CUDA_VERSION__12.8"""
        )

        self.assertEqual(gpu_status, "driver_ok")
        self.assertIn("CUDA 12.8", gpu_info)
