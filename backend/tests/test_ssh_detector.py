import unittest

from app.core.ssh_detector import CONSOLIDATED_PROBE_SCRIPT, _summarize_cpu_info, _summarize_cpu_topology, _summarize_disk_inventory, _summarize_gpu_info


class SshDetectorTests(unittest.TestCase):
    def test_disk_probe_requests_name_to_preserve_lsblk_parent_child_relationships(self) -> None:
        self.assertIn(
            "lsblk --json --bytes --output NAME,PATH,SIZE,TYPE,MOUNTPOINTS",
            CONSOLIDATED_PROBE_SCRIPT,
        )

    def test_probe_retries_nvidia_smi_while_driver_is_starting(self) -> None:
        self.assertIn("for smi_attempt in 1 2 3", CONSOLIDATED_PROBE_SCRIPT)

    def test_summarize_cpu_info_supports_localized_lscpu_output(self) -> None:
        raw = """架构： x86_64
CPU： 192
型号名称： AMD Ryzen Threadripper PRO 7995WX 96-Cores
"""

        self.assertEqual(
            _summarize_cpu_info(raw),
            "AMD Ryzen Threadripper PRO 7995WX 96-Cores / 192C",
        )

    def test_summarize_cpu_topology_keeps_socket_core_and_thread_counts_distinct(self) -> None:
        raw = """CPU(s):                192
On-line CPU(s) list:   0-191
Thread(s) per core:    2
Core(s) per socket:    48
Socket(s):             2
Model name:             Intel(R) Xeon(R) Platinum 8457C
"""

        self.assertEqual(
            _summarize_cpu_topology(raw),
            {"cpu_sockets": 2, "cpu_physical_cores": 96, "cpu_logical_threads": 192},
        )

    def test_summarize_cpu_topology_uses_logical_cpu_count_when_smt_is_disabled(self) -> None:
        raw = """CPU(s):                32
Thread(s) per core:    1
Core(s) per socket:    32
Socket(s):             1
Model name:             AMD EPYC 75F3 32-Core Processor
"""

        self.assertEqual(
            _summarize_cpu_topology(raw),
            {"cpu_sockets": 1, "cpu_physical_cores": 32, "cpu_logical_threads": 32},
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

    def test_summarize_disk_inventory_keeps_unmounted_physical_disks(self) -> None:
        raw = """Filesystem     Type   Size  Used Avail Use% Mounted on
/dev/nvme0n1p2 ext4   916G   27G  842G   4% /
/dev/nvme0n1p1 vfat   511M  6.1M  505M   2% /boot/efi
__HPROBE_DISK_BLOCK__
{
  "blockdevices": [
    {"path": "/dev/sda", "size": 16060580270080, "type": "disk", "mountpoints": [null]},
    {"path": "/dev/nvme0n1", "size": 1000204886016, "type": "disk", "mountpoints": [null], "children": [
      {"path": "/dev/nvme0n1p2", "size": 999000000000, "type": "part", "mountpoints": ["/"]}
    ]}
  ]
}"""

        self.assertEqual(
            _summarize_disk_inventory(raw),
            {
                "mounted_filesystems": [
                    {"device": "/dev/nvme0n1p2", "filesystem_type": "ext4", "size": "916G", "used": "27G", "available": "842G", "use_percent": "4%", "mountpoint": "/"},
                    {"device": "/dev/nvme0n1p1", "filesystem_type": "vfat", "size": "511M", "used": "6.1M", "available": "505M", "use_percent": "2%", "mountpoint": "/boot/efi"},
                ],
                "unmounted_disks": [{"device": "/dev/sda", "size": "14.6T"}],
            },
        )
