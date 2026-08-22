import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from app.core.ssh_detector import CONSOLIDATED_PROBE_SCRIPT, _classify_disk_media_type, _parse_disk_media_types, _summarize_cpu_info, _summarize_cpu_topology, _summarize_disk_inventory, _summarize_gpu_info


class SshDetectorTests(unittest.TestCase):
    def test_disk_probe_requests_name_to_preserve_lsblk_parent_child_relationships(self) -> None:
        self.assertIn(
            "lsblk --json --bytes --output NAME,PATH,SIZE,TYPE,MOUNTPOINTS,ROTA,TRAN,MODEL",
            CONSOLIDATED_PROBE_SCRIPT,
        )

    def test_raid_controller_logical_disk_is_not_classified_as_hdd(self) -> None:
        self.assertEqual(
            _classify_disk_media_type({"model": "MR9361-8i", "rota": True}),
            "RAID",
        )

    def test_raid_media_type_is_inherited_by_its_partitions(self) -> None:
        media_types = _parse_disk_media_types("""{
          "blockdevices": [{
            "path": "/dev/sda", "type": "disk", "model": "MR9361-8i", "rota": true,
            "children": [{"path": "/dev/sda2", "type": "part", "rota": true}]
          }]
        }""")

        self.assertEqual(media_types["/dev/sda2"], "RAID")

    def test_probe_retries_nvidia_smi_while_driver_is_starting(self) -> None:
        self.assertIn("for smi_attempt in 1 2 3", CONSOLIDATED_PROBE_SCRIPT)

    def test_probe_keeps_parseable_nvidia_smi_output_when_command_exceeds_timeout(self) -> None:
        self.assertIn(
            "if [ -n \"$smi_candidate\" ] && printf '%s\\n' \"$smi_candidate\" | grep -Eq",
            CONSOLIDATED_PROBE_SCRIPT,
        )

    def test_probe_keeps_gpu_data_emitted_before_nvidia_smi_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            fake_binary = Path(temporary_dir) / "nvidia-smi"
            fake_binary.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' '0, NVIDIA L20, 580.159.04, 46068, 0, 35, 0'\n"
                "sleep 4\n",
                encoding="utf-8",
            )
            fake_binary.chmod(0o755)
            env = {**os.environ, "PATH": f"{temporary_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", "-c", CONSOLIDATED_PROBE_SCRIPT],
                env=env,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("0, NVIDIA L20, 580.159.04", result.stdout)
        self.assertNotIn("__NVIDIA_SMI_FAILED__", result.stdout)
        self.assertNotIn(
            'nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu --format=csv,noheader,nounits 2>/dev/null)" && [ -n "$smi_output" ]',
            CONSOLIDATED_PROBE_SCRIPT,
        )

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
/dev/sda1 ext4 14T    666M  14T   1% /data
__HPROBE_DISK_BLOCK__
{
  "blockdevices": [
    {"path": "/dev/sda", "size": 16060580270080, "type": "disk", "mountpoints": [null], "rota": true, "tran": "sata", "children": [
      {"path": "/dev/sda1", "size": 16060580200000, "type": "part", "mountpoints": ["/data"], "rota": true, "tran": "sata"}
    ]},
    {"path": "/dev/nvme0n1", "size": 1000204886016, "type": "disk", "mountpoints": [null], "rota": false, "tran": "nvme", "children": [
      {"path": "/dev/nvme0n1p2", "size": 999000000000, "type": "part", "mountpoints": ["/"], "rota": false, "tran": "nvme"}
    ]},
    {"path": "/dev/sdb", "size": 1000204886016, "type": "disk", "mountpoints": [null], "rota": false, "tran": "sas"}
  ]
}"""

        self.assertEqual(
            _summarize_disk_inventory(raw),
            {
                "mounted_filesystems": [
                    {"device": "/dev/nvme0n1p2", "filesystem_type": "ext4", "size": "916G", "used": "27G", "available": "842G", "use_percent": "4%", "mountpoint": "/", "media_type": "SSD", "interface_type": "NVMe", "physical_device": "/dev/nvme0n1"},
                    {"device": "/dev/nvme0n1p1", "filesystem_type": "vfat", "size": "511M", "used": "6.1M", "available": "505M", "use_percent": "2%", "mountpoint": "/boot/efi", "media_type": "SSD", "interface_type": "NVMe", "physical_device": "/dev/nvme0n1p1"},
                    {"device": "/dev/sda1", "filesystem_type": "ext4", "size": "14T", "used": "666M", "available": "14T", "use_percent": "1%", "mountpoint": "/data", "media_type": "HDD", "interface_type": "SATA", "physical_device": "/dev/sda"},
                ],
                "unmounted_disks": [{"device": "/dev/sdb", "size": "931.5G", "media_type": "SSD", "interface_type": "SAS"}],
            },
        )

    def test_summarize_disk_inventory_records_the_physical_disk_for_lvm_mounts(self) -> None:
        raw = """Filesystem     Type   Size  Used Avail Use% Mounted on
/dev/mapper/vg_data-docker xfs 500G  3G  497G  1% /var/lib/docker
/dev/mapper/vg_data-data xfs 1T  7G  993G  1% /data
__HPROBE_DISK_BLOCK__
{"blockdevices": [{"path": "/dev/nvme0n1", "type": "disk", "rota": false, "tran": "nvme", "children": [
  {"path": "/dev/nvme0n1p3", "type": "part", "children": [
    {"path": "/dev/mapper/vg_data-docker", "type": "lvm"},
    {"path": "/dev/mapper/vg_data-data", "type": "lvm"}
  ]}
]}]}"""

        inventory = _summarize_disk_inventory(raw)

        self.assertEqual(
            [filesystem["physical_device"] for filesystem in inventory["mounted_filesystems"]],
            ["/dev/nvme0n1", "/dev/nvme0n1"],
        )
