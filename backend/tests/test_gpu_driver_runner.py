import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import Mock, patch

from app.core.gpu_driver_runner import (
    _optional_param_text,
    _start_remote_install,
    build_rocky9_install_script,
    build_rocky9_pre_reboot_script,
    installed_driver_matches_target,
    list_library_drivers,
    driver_version_from_filename,
    should_reboot_for_gpu_driver,
    should_skip_existing_driver,
    resolve_gpu_driver_os_profile,
    build_ubuntu_pre_reboot_script,
    build_ubuntu_install_script,
    validate_library_driver_filename,
)


class GpuDriverRunnerTests(unittest.TestCase):
    def test_optional_driver_parameter_treats_json_null_as_empty(self) -> None:
        self.assertEqual(_optional_param_text(None), "")
        self.assertEqual(_optional_param_text("  abc123  "), "abc123")

    def test_install_script_preserves_required_rocky_flow(self) -> None:
        script = build_rocky9_install_script()
        self.assertIn('kernel-devel-$(uname -r)', script)
        self.assertIn('kernel-headers-$(uname -r)', script)
        self.assertIn('--kernel-source-path="/usr/src/kernels/$(uname -r)"', script)
        self.assertIn('--no-cc-version-check --no-opengl-files --disable-nouveau --dkms', script)
        self.assertIn('--no-questions --accept-license --ui=none', script)
        self.assertIn('nvidia-smi', script)
        self.assertNotIn('lsmod | grep nvidia', script)
        self.assertNotIn('glxinfo', script)

    def test_driver_script_uses_uploaded_file_without_download(self) -> None:
        script = build_rocky9_install_script()
        self.assertNotIn("curl --fail", script)
        self.assertIn("检查 NVIDIA 驱动文件", script)

    def test_background_installer_detaches_stdin_and_records_pid_in_task_dir(self) -> None:
        executor = Mock()
        _start_remote_install(executor, "/root/hpcdeploy/tasks/gpu-driver/task-1")
        command = executor.exec_simple.call_args.args[0]
        self.assertIn("cd '/root/hpcdeploy/tasks/gpu-driver/task-1'", command)
        self.assertIn("</dev/null > gpu-driver-install.log 2>&1", command)
        self.assertIn("echo $! > .gpu-driver.pid", command)

    def test_pre_reboot_script_updates_and_disables_nouveau(self) -> None:
        script = build_rocky9_pre_reboot_script()
        self.assertIn('sudo yum update -y', script)
        self.assertIn('blacklist nouveau', script)
        self.assertIn('sudo dracut --force', script)

    def test_preparation_skips_reboot_steps_when_nouveau_is_absent(self) -> None:
        script = build_rocky9_pre_reboot_script(disable_nouveau=False)
        self.assertIn('Nouveau 未加载，跳过禁用与重启', script)
        self.assertNotIn('sudo dracut --force', script)

    def test_installed_default_driver_version_can_skip_reinstall(self) -> None:
        self.assertTrue(installed_driver_matches_target("580.159.04\n", "580.159.04"))
        self.assertTrue(installed_driver_matches_target("580.159.04\n580.159.04\n", "580.159.04"))
        self.assertFalse(installed_driver_matches_target("580.173.02\n", "580.159.04"))
        self.assertFalse(installed_driver_matches_target("", "580.159.04"))

    def test_library_driver_requires_linux_nvidia_run_filename(self) -> None:
        self.assertEqual(
            validate_library_driver_filename("NVIDIA-Linux-x86_64-580.173.02.run"),
            "NVIDIA-Linux-x86_64-580.173.02.run",
        )
        with self.assertRaisesRegex(ValueError, "NVIDIA-Linux-x86_64"):
            validate_library_driver_filename("NVIDIA-Windows-x86_64-580.173.02.exe")

    def test_library_lists_multiple_versioned_drivers_with_original_filenames(self) -> None:
        with TemporaryDirectory() as temp_dir, patch("app.core.gpu_driver_runner.GPU_DRIVER_LIBRARY_ROOT", Path(temp_dir)):
            root = Path(temp_dir)
            for driver_id, filename in (
                ("a" * 24, "NVIDIA-Linux-x86_64-580.159.04.run"),
                ("b" * 24, "NVIDIA-Linux-x86_64-580.173.02.run"),
            ):
                entry = root / "geforce" / driver_id
                entry.mkdir(parents=True)
                (entry / filename).write_bytes(b"driver")

            records = list_library_drivers()

        self.assertEqual(len(records), 2)
        self.assertEqual({record["driver_type"] for record in records}, {"geforce"})
        self.assertEqual(
            {record["filename"] for record in records},
            {"NVIDIA-Linux-x86_64-580.159.04.run", "NVIDIA-Linux-x86_64-580.173.02.run"},
        )

    def test_library_driver_version_is_derived_from_original_filename(self) -> None:
        self.assertEqual(
            driver_version_from_filename("NVIDIA-Linux-x86_64-580.173.02.run"),
            "580.173.02",
        )

    def test_existing_nvidia_driver_skips_installation_unless_forced(self) -> None:
        self.assertTrue(should_skip_existing_driver(nvidia_smi_available=True, force_install=False))
        self.assertFalse(should_skip_existing_driver(nvidia_smi_available=True, force_install=True))
        self.assertFalse(should_skip_existing_driver(nvidia_smi_available=False, force_install=False))

    def test_reboot_is_required_for_nouveau_or_new_default_kernel(self) -> None:
        self.assertTrue(should_reboot_for_gpu_driver(nouveau_loaded=True, kernel_reboot_required=False))
        self.assertTrue(should_reboot_for_gpu_driver(nouveau_loaded=False, kernel_reboot_required=True))
        self.assertFalse(should_reboot_for_gpu_driver(nouveau_loaded=False, kernel_reboot_required=False))

    def test_driver_os_profile_supports_rocky9_and_supported_ubuntu_releases(self) -> None:
        self.assertEqual(resolve_gpu_driver_os_profile("Rocky Linux 9.4 (Blue Onyx)"), "rocky9")
        self.assertEqual(resolve_gpu_driver_os_profile("Ubuntu 22.04.5 LTS"), "ubuntu22")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            resolve_gpu_driver_os_profile("Debian GNU/Linux 12")

    def test_ubuntu_scripts_install_dependencies_and_only_verify_nvidia_smi(self) -> None:
        preparation = build_ubuntu_pre_reboot_script(disable_nouveau=True)
        installer = build_ubuntu_install_script()
        self.assertIn("apt-get update", preparation)
        self.assertIn("linux-headers-$(uname -r)", preparation)
        self.assertIn("update-initramfs -u", preparation)
        self.assertIn("--kernel-source-path=/lib/modules/$(uname -r)/build", installer)
        self.assertIn("nvidia-smi", installer)
        self.assertNotIn("lsmod | grep nvidia", installer)
        self.assertNotIn("compute_cap", installer)


if __name__ == "__main__":
    unittest.main()
