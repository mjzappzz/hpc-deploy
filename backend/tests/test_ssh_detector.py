import unittest

from app.core.ssh_detector import _summarize_gpu_info


class SshDetectorTests(unittest.TestCase):
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
