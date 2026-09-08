import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import Mock, patch

from app.core.gpu_driver_runner import (
    _optional_param_text,
    _prepare_rocky_kernel_maintenance_reboot,
    _run_rocky_release_lock,
    _start_remote_install,
    build_rocky9_kernel_maintenance_script,
    build_rocky9_install_script,
    build_rocky9_pre_reboot_script,
    installed_driver_matches_target,
    kernel_maintenance_boot_matches,
    list_library_drivers,
    driver_version_from_filename,
    should_reboot_for_gpu_driver,
    should_reboot_after_driver_install,
    should_run_kernel_maintenance,
    should_schedule_post_install_reboot,
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
        self.assertIn('--kernel-module-type="$kernel_module_type"', script)
        self.assertIn('--allow-installation-with-running-driver', script)
        self.assertIn("awk '$0 == \"open\" || $0 == \"proprietary\" { result=$0 } END { print result }'", script)
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

    def test_pre_reboot_script_does_not_mutate_missing_kernel_dependencies(self) -> None:
        script = build_rocky9_pre_reboot_script()
        self.assertIn('running_kernel="$(uname -r)"', script)
        self.assertNotIn('kernel-devel-${running_kernel}', script)
        self.assertNotIn('kernel-headers-${running_kernel}', script)
        self.assertNotIn('yum update', script)
        self.assertIn('blacklist nouveau', script)
        self.assertIn('sudo dracut --force', script)

    def test_kernel_maintenance_requires_explicit_authorization(self) -> None:
        self.assertFalse(should_run_kernel_maintenance(
            exact_development_packages_available=False,
            allowed=False,
        ))
        self.assertTrue(should_run_kernel_maintenance(
            exact_development_packages_available=False,
            allowed=True,
        ))
        self.assertFalse(should_run_kernel_maintenance(
            exact_development_packages_available=True,
            allowed=True,
        ))

    def test_kernel_maintenance_uses_exact_packages_without_a_full_update(self) -> None:
        script = build_rocky9_kernel_maintenance_script()
        self.assertIn("dnf -q repoquery --latest-limit=1", script)
        self.assertIn('"kernel-${candidate}"', script)
        self.assertIn('"kernel-core-${candidate}"', script)
        self.assertIn('"kernel-modules-${candidate}"', script)
        self.assertIn('"kernel-devel-${candidate}"', script)
        self.assertIn('"kernel-headers-${candidate}"', script)
        self.assertIn("dnf versionlock delete 'kernel*'", script)
        self.assertNotIn("yum update", script)
        self.assertNotIn("dnf update", script)

    def test_kernel_maintenance_validates_initramfs_before_changing_default_boot(self) -> None:
        script = build_rocky9_kernel_maintenance_script()
        self.assertIn('sudo dracut --force --kver "$candidate"', script)
        self.assertIn('test -s "$image"', script)
        self.assertIn('root_source="$(findmnt -n -o SOURCE /)"', script)
        self.assertIn('required_modules+=(dm-mod lvm)', script)
        self.assertIn('required_modules+=(nvme)', script)
        self.assertIn('sudo lsinitrd "$image"', script)
        self.assertIn('restore_before_boot', script)
        self.assertIn('sudo grubby --set-default "/boot/vmlinuz-${candidate}"', script)
        self.assertLess(
            script.index('test -s "$image"'),
            script.index('sudo grubby --set-default "/boot/vmlinuz-${candidate}"'),
        )

    def test_kernel_maintenance_only_resumes_after_booting_the_candidate(self) -> None:
        self.assertTrue(kernel_maintenance_boot_matches(
            candidate="5.14.0-427.42.1.el9_4.x86_64",
            running_kernel="5.14.0-427.42.1.el9_4.x86_64",
        ))
        self.assertFalse(kernel_maintenance_boot_matches(
            candidate="5.14.0-427.42.1.el9_4.x86_64",
            running_kernel="5.14.0-427.13.1.el9_4.x86_64",
        ))

    def test_kernel_maintenance_persists_candidate_and_waiting_reboot_phase(self) -> None:
        task = Mock(task_id="task-kernel", remote_work_dir="/tmp/task-kernel", params={})
        task.params = {}
        params_updates: list[dict[str, object]] = []

        with (
            patch("app.core.gpu_driver_runner._run_script", return_value=0),
            patch("app.core.gpu_driver_runner._read_remote_required_file", side_effect=[
                "5.14.0-427.42.1.el9_4.x86_64",
                "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64",
            ]),
            patch("app.core.gpu_driver_runner._read_boot_id", return_value="boot-before"),
            patch("app.core.gpu_driver_runner._update_params", side_effect=lambda _db, _task, **values: params_updates.append(values)),
            patch("app.core.gpu_driver_runner._set_status"),
            patch("app.core.gpu_driver_runner._schedule_reboot") as schedule_reboot,
            patch("app.core.gpu_driver_runner._log"),
        ):
            candidate, previous_default = _prepare_rocky_kernel_maintenance_reboot(Mock(), task, Mock())

        self.assertEqual(candidate, "5.14.0-427.42.1.el9_4.x86_64")
        self.assertEqual(previous_default, "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64")
        self.assertEqual(params_updates[0]["gpu_driver_phase"], "waiting_kernel_maintenance_reboot")
        self.assertEqual(params_updates[0]["gpu_driver_kernel_candidate"], candidate)
        schedule_reboot.assert_called_once()

    def test_kernel_maintenance_relocks_the_verified_kernel_with_sudo(self) -> None:
        executor = Mock()
        executor.exec_command_in_dir.return_value = 0
        with TemporaryDirectory() as temp_dir:
            release_lock = Path(temp_dir) / "lock_linux_release.sh"
            release_lock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            with (
                patch("app.core.gpu_driver_runner.GPU_DRIVER_RELEASE_LOCK_SCRIPT", release_lock),
                patch("app.core.gpu_driver_runner._log"),
            ):
                _run_rocky_release_lock(executor, "/tmp/task-kernel", "task-kernel", Mock())

        command = executor.exec_command_in_dir.call_args.args[0]
        self.assertIn("sudo -n bash", command)

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

    def test_forced_upgrade_of_a_running_driver_reboots_before_final_verification(self) -> None:
        self.assertTrue(should_reboot_after_driver_install(force_install=True, nvidia_smi_available=True))
        self.assertFalse(should_reboot_after_driver_install(force_install=False, nvidia_smi_available=True))
        self.assertFalse(should_reboot_after_driver_install(force_install=True, nvidia_smi_available=False))

    def test_successful_install_with_inactive_driver_reboots_before_verification(self) -> None:
        self.assertTrue(should_schedule_post_install_reboot(
            force_install=False,
            activation_reboot_required=True,
        ))
        self.assertTrue(should_schedule_post_install_reboot(
            force_install=True,
            activation_reboot_required=False,
        ))
        self.assertFalse(should_schedule_post_install_reboot(
            force_install=False,
            activation_reboot_required=False,
        ))

    def test_install_scripts_mark_driver_activation_reboot_requirement(self) -> None:
        for script in (build_rocky9_install_script(), build_ubuntu_install_script()):
            self.assertIn(".gpu-driver.activation-reboot-required", script)
            self.assertIn("NVIDIA driver installed but is not active until reboot", script)

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
        self.assertIn("--no-questions --accept-license --ui=none", installer)
        self.assertIn('--kernel-module-type="$kernel_module_type"', installer)
        self.assertIn('--allow-installation-with-running-driver', installer)
        self.assertIn("awk '$0 == \"open\" || $0 == \"proprietary\" { result=$0 } END { print result }'", installer)
        self.assertIn("nvidia-smi", installer)
        self.assertNotIn("lsmod | grep nvidia", installer)
        self.assertNotIn("compute_cap", installer)


if __name__ == "__main__":
    unittest.main()
