import base64
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import ANY, Mock, patch

from app.core.gpu_driver_runner import (
    _monitor_remote_install,
    _optional_param_text,
    _prepare_rocky_kernel_maintenance_reboot,
    _restore_default_kernel,
    _run_rocky_release_lock,
    _run_script,
    _schedule_reboot,
    _start_remote_install,
    build_rocky9_kernel_maintenance_script,
    build_rocky9_install_script,
    build_rocky9_pre_reboot_script,
    installed_driver_matches_target,
    kernel_maintenance_boot_matches,
    list_library_drivers,
    driver_version_from_filename,
    run_rocky9_gpu_driver_task,
    should_reboot_for_gpu_driver,
    should_reboot_after_driver_install,
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

    def test_background_installer_uploads_as_user_before_root_launch(self) -> None:
        executor = Mock()
        events: list[str] = []

        def upload(*_args, **_kwargs):
            events.append("upload")
            return 0, "", ""

        def launch(*_args, **_kwargs):
            events.append("launch")
            return 0, "", ""

        executor.exec_capture.side_effect = upload
        executor.exec_sudo.side_effect = launch

        _start_remote_install(executor, "/home/deploy/gpu task", "echo installer", password="saved-secret")

        self.assertEqual(events, ["upload", "launch"])
        upload = executor.exec_capture.call_args.args[0]
        launch = executor.exec_sudo.call_args.args[0]
        self.assertIn("gpu-driver-install.sh", upload)
        self.assertIn(base64.b64encode(b"echo installer").decode("ascii"), upload)
        self.assertNotIn("sudo", upload)
        self.assertIn("umask 022", launch)
        self.assertIn("nohup setsid bash -c", launch)
        self.assertIn("</dev/null > gpu-driver-install.log 2>&1", launch)
        self.assertIn('"$pid" > .gpu-driver.pid', launch)
        self.assertIn('"$pid" > .hpcdeploy.pid', launch)
        self.assertNotIn("saved-secret", upload + launch)
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "saved-secret")

    def test_installer_upload_and_root_launch_report_distinct_failures(self) -> None:
        executor = Mock()
        executor.exec_capture.return_value = (1, "", "upload denied")
        with self.assertRaisesRegex(RuntimeError, "upload NVIDIA installer script: upload denied"):
            _start_remote_install(executor, "/home/deploy/task", "echo installer", password="secret")
        executor.exec_sudo.assert_not_called()

        executor.exec_capture.return_value = (0, "", "")
        executor.exec_sudo.return_value = (1, "", "sudo: authentication failed")
        with self.assertRaisesRegex(RuntimeError, "launch NVIDIA installer with sudo: sudo: authentication failed"):
            _start_remote_install(executor, "/home/deploy/task", "echo installer", password="secret")

    def test_streamed_preparation_uses_root_with_stdin_password(self) -> None:
        executor = Mock()
        executor.exec_sudo_in_dir.return_value = 0
        logger = Mock()
        script = "echo preparation"

        self.assertEqual(_run_script(executor, "/home/deploy/task", script, 7200, logger, password="secret"), 0)

        executor.exec_sudo_in_dir.assert_called_once()
        command, cwd = executor.exec_sudo_in_dir.call_args.args
        self.assertEqual(cwd, "/home/deploy/task")
        self.assertIn(base64.b64encode(script.encode()).decode("ascii"), command)
        self.assertIn("umask 022", command)
        self.assertNotIn("secret", command)
        self.assertEqual(executor.exec_sudo_in_dir.call_args.kwargs["password"], "secret")
        self.assertIs(executor.exec_sudo_in_dir.call_args.kwargs["on_stderr_line"], logger)

    def test_reboot_uses_saved_sudo_credential_and_reports_denial(self) -> None:
        executor = Mock()
        executor.exec_sudo.return_value = (0, "", "")
        _schedule_reboot(executor, password="secret")
        command = executor.exec_sudo.call_args.args[0]
        self.assertIn("systemctl reboot", command)
        self.assertIn("</dev/null >/dev/null 2>&1 &", command)
        self.assertNotIn("secret", command)
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "secret")

        executor.exec_sudo.return_value = (1, "", "sudo: a password is required")
        with self.assertRaisesRegex(RuntimeError, "schedule NVIDIA driver reboot with sudo"):
            _schedule_reboot(executor, password="wrong")

    def test_monitor_observes_detached_installer_then_marks_success(self) -> None:
        with TemporaryDirectory() as temp_dir:
            task = Mock(task_id="task-root", remote_work_dir=temp_dir, params={}, status="RUNNING")
            work_dir = Path(temp_dir)
            (work_dir / ".gpu-driver.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            (work_dir / "gpu-driver-install.log").write_text("driver installed\n", encoding="utf-8")
            executor = Mock()

            def capture(command, *, timeout_seconds):
                completed = subprocess.run(
                    ["sh", "-c", command], capture_output=True, text=True, timeout=timeout_seconds,
                    check=False,
                )
                return completed.returncode, completed.stdout.strip(), completed.stderr.strip()

            executor.exec_capture.side_effect = capture
            db = Mock()
            with (
                patch("app.core.gpu_driver_runner.sleep", side_effect=lambda _seconds: (
                    work_dir / ".gpu-driver.exit"
                ).write_text("0\n", encoding="utf-8")) as sleep,
                patch("app.core.gpu_driver_runner._log") as log,
                patch("app.core.gpu_driver_runner.ws_manager"),
            ):
                self.assertFalse(_monitor_remote_install(db, task, executor, password="secret"))

        self.assertEqual(task.status, "SUCCESS")
        self.assertEqual(task.exit_code, 0)
        sleep.assert_called_once_with(5)
        status_command = executor.exec_capture.call_args_list[0].args[0]
        self.assertNotIn("kill -0", status_command)
        self.assertNotIn("secret", status_command)
        log.assert_called_once_with(db, "task-root", "INFO", "driver installed")

    def test_monitor_recovery_schedules_activation_reboot_with_saved_password(self) -> None:
        task = Mock(task_id="task-reboot", remote_work_dir="/home/deploy/task-reboot", status="RUNNING")
        task.params = {}
        executor = Mock()
        executor.exec_capture.side_effect = [(0, "9", ""), (0, "", ""), (0, "driver awaiting reboot", "")]
        executor.exec_sudo.return_value = (0, "", "")
        db = Mock()
        with (
            patch("app.core.gpu_driver_runner._read_boot_id", return_value="boot-before"),
            patch("app.core.gpu_driver_runner._log"),
            patch("app.core.gpu_driver_runner.ws_manager"),
        ):
            self.assertTrue(_monitor_remote_install(db, task, executor, password="secret"))

        self.assertEqual(task.params["gpu_driver_phase"], "waiting_post_install_reboot")
        self.assertEqual(task.params["gpu_driver_boot_id"], "boot-before")
        self.assertEqual(task.status, "WAITING_REBOOT")
        self.assertIn("systemctl reboot", executor.exec_sudo.call_args.args[0])
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "secret")

    def test_resume_after_preparation_reboot_uploads_and_launches_with_saved_password(self) -> None:
        task = Mock(
            task_id="task-recovery", task_type="gpu_driver", status="WAITING_REBOOT",
            server_id=7, remote_work_dir="/home/deploy/task-recovery", start_time=None,
        )
        task.params = {
            "driver_upload_id": "a" * 24,
            "gpu_driver_phase": "waiting_reboot",
            "os_profile": "ubuntu22",
        }
        server = Mock(password="saved-secret", os_info="Ubuntu 22.04")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = task
        db.get.return_value = server
        executor = Mock()
        executor.get_remote_home.return_value = "/home/deploy"
        executor.exec_capture.return_value = (0, "", "")
        executor.exec_sudo.return_value = (0, "", "")
        with (
            patch("app.core.gpu_driver_runner.SessionLocal", return_value=db),
            patch("app.core.gpu_driver_runner.SSHExecutor", return_value=executor),
            patch("app.core.gpu_driver_runner.resolve_uploaded_driver", return_value=Path("/tmp/driver.run")),
            patch("app.core.gpu_driver_runner._wait_for_reboot", return_value=True),
            patch("app.core.gpu_driver_runner._monitor_remote_install", return_value=False) as monitor,
            patch("app.core.gpu_driver_runner._log"),
            patch("app.core.gpu_driver_runner.ws_manager"),
        ):
            run_rocky9_gpu_driver_task("task-recovery")

        self.assertEqual(executor.connect.call_args.kwargs["password"], "saved-secret")
        executor.upload_file.assert_called_once_with(
            "/tmp/driver.run", "/home/deploy/task-recovery/nvidia-rocky9-driver.run"
        )
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "saved-secret")
        self.assertNotIn("saved-secret", executor.exec_sudo.call_args.args[0])
        self.assertEqual(task.params["gpu_driver_phase"], "installing")
        self.assertEqual(monitor.call_args.kwargs["password"], "saved-secret")

    def test_initial_install_prepares_as_root_without_passwordless_sudo(self) -> None:
        task = Mock(
            task_id="task-initial", task_type="gpu_driver", status="PENDING",
            server_id=7, remote_work_dir="/home/deploy/task-initial", start_time=None,
        )
        task.params = {"driver_upload_id": "a" * 24, "os_profile": "ubuntu22"}
        server = Mock(password="saved-secret", os_info="Ubuntu 22.04")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = task
        db.get.return_value = server
        executor = Mock()
        executor.get_remote_home.return_value = "/home/deploy"
        executor.exec_sudo_in_dir.return_value = 0
        executor.exec_sudo.return_value = (0, "", "")

        def capture(command, *, timeout_seconds):
            if command.startswith("nvidia-smi") or command.startswith("lsmod"):
                return 1, "", ""
            return 0, "", ""

        executor.exec_capture.side_effect = capture
        with (
            patch("app.core.gpu_driver_runner.SessionLocal", return_value=db),
            patch("app.core.gpu_driver_runner.SSHExecutor", return_value=executor),
            patch("app.core.gpu_driver_runner.resolve_uploaded_driver", return_value=Path("/tmp/driver.run")),
            patch("app.core.gpu_driver_runner._monitor_remote_install", return_value=False) as monitor,
            patch("app.core.gpu_driver_runner._log"),
            patch("app.core.gpu_driver_runner.ws_manager"),
        ):
            run_rocky9_gpu_driver_task("task-initial")

        streamed = executor.exec_sudo_in_dir.call_args
        self.assertEqual(streamed.kwargs["password"], "saved-secret")
        encoded_script = streamed.args[0].split("printf %s '", 1)[1].split("'", 1)[0]
        self.assertIn("sudo -n true", base64.b64decode(encoded_script).decode("utf-8"))
        self.assertNotIn("saved-secret", streamed.args[0])
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "saved-secret")
        self.assertEqual(task.params["gpu_driver_phase"], "installing")
        self.assertEqual(monitor.call_args.kwargs["password"], "saved-secret")

    def test_pre_reboot_script_does_not_mutate_missing_kernel_dependencies(self) -> None:
        script = build_rocky9_pre_reboot_script()
        self.assertIn('running_kernel="$(uname -r)"', script)
        self.assertNotIn('kernel-devel-${running_kernel}', script)
        self.assertNotIn('kernel-headers-${running_kernel}', script)
        self.assertNotIn('yum update', script)
        self.assertIn('blacklist nouveau', script)
        self.assertIn('sudo dracut --force', script)

    def test_missing_kernel_packages_start_maintenance_without_opt_in(self) -> None:
        task = Mock(
            task_id="task-rocky", task_type="gpu_driver", status="PENDING",
            server_id=7, remote_work_dir="/home/deploy/task-rocky", start_time=None,
        )
        task.params = {"driver_upload_id": "a" * 24, "os_profile": "rocky9"}
        server = Mock(password=None, os_info="Rocky Linux 9.4")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = task
        db.get.return_value = server
        executor = Mock()
        executor.get_remote_home.return_value = "/home/deploy"
        executor.exec_simple.return_value = "5.14.0-427.42.1.el9_4.x86_64"

        def capture(command, *, timeout_seconds):
            if command.startswith("nvidia-smi"):
                return 1, "", ""
            if command.startswith("rpm -q"):
                return 1, "", ""
            if command.startswith("lsmod"):
                return 1, "", ""
            return 0, "", ""

        executor.exec_capture.side_effect = capture
        with (
            patch("app.core.gpu_driver_runner.SessionLocal", return_value=db),
            patch("app.core.gpu_driver_runner.SSHExecutor", return_value=executor),
            patch("app.core.gpu_driver_runner.resolve_uploaded_driver", return_value=Path("/tmp/driver.run")),
            patch(
                "app.core.gpu_driver_runner._prepare_rocky_kernel_maintenance_reboot",
                return_value=("5.14.0-427.42.1.el9_4.x86_64", "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64"),
            ) as prepare,
            patch("app.core.gpu_driver_runner._wait_for_reboot", return_value=True),
            patch("app.core.gpu_driver_runner._run_rocky_release_lock"),
            patch("app.core.gpu_driver_runner._run_script", return_value=0),
            patch("app.core.gpu_driver_runner._start_remote_install") as start_install,
            patch("app.core.gpu_driver_runner._monitor_remote_install", return_value=False),
            patch("app.core.gpu_driver_runner._update_params"),
            patch("app.core.gpu_driver_runner._set_status"),
            patch("app.core.gpu_driver_runner._log"),
            patch("app.core.gpu_driver_runner.ws_manager"),
        ):
            run_rocky9_gpu_driver_task("task-rocky")

        prepare.assert_called_once()
        start_install.assert_called_once()

    def test_kernel_maintenance_uses_exact_packages_without_a_full_update(self) -> None:
        script = build_rocky9_kernel_maintenance_script()
        self.assertIn("dnf -q repoquery --latest-limit=1", script)
        self.assertIn('candidate="$candidate_full"', script)
        self.assertIn('candidate_pkg="${candidate_full%.*}"', script)
        self.assertIn('"kernel-${candidate_pkg}"', script)
        self.assertIn('"kernel-core-${candidate_pkg}"', script)
        self.assertIn('"kernel-modules-${candidate_pkg}"', script)
        self.assertIn('"kernel-devel-${candidate_pkg}"', script)
        self.assertIn('"kernel-headers-${candidate_pkg}"', script)
        self.assertIn("dnf versionlock delete 'kernel*'", script)
        self.assertNotIn("yum update", script)
        self.assertNotIn("dnf update", script)

    def test_kernel_maintenance_validates_initramfs_before_changing_default_boot(self) -> None:
        script = build_rocky9_kernel_maintenance_script()
        self.assertIn('candidate="$candidate_full"', script)
        self.assertIn('candidate_pkg="${candidate_full%.*}"', script)
        self.assertIn('sudo dracut --force --kver "$candidate"', script)
        self.assertIn('test -s "$image"', script)
        self.assertIn('root_source="$(findmnt -n -o SOURCE /)"', script)
        self.assertIn('required_modules+=(dm-mod lvm)', script)
        self.assertIn('required_modules+=(nvme)', script)
        self.assertIn('initramfs_listing="$(sudo lsinitrd "$image")"', script)
        self.assertNotIn('sudo lsinitrd "$image" | grep', script)
        self.assertIn('<<< "$initramfs_listing"', script)
        self.assertIn('restore_before_boot', script)
        self.assertIn('sudo grubby --set-default "/boot/vmlinuz-${candidate}"', script)
        self.assertIn('sync_uefi_saved_entry', script)
        self.assertIn('sudo grub2-editenv "$dir/grubenv" set saved_entry="$entry"', script)
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
            patch("app.core.gpu_driver_runner._run_script", return_value=0) as run_script,
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
            candidate, previous_default = _prepare_rocky_kernel_maintenance_reboot(Mock(), task, Mock(), password="secret")

        self.assertEqual(candidate, "5.14.0-427.42.1.el9_4.x86_64")
        self.assertEqual(previous_default, "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64")
        self.assertEqual(params_updates[0]["gpu_driver_phase"], "waiting_kernel_maintenance_reboot")
        self.assertEqual(params_updates[0]["gpu_driver_kernel_candidate"], candidate)
        schedule_reboot.assert_called_once_with(ANY, password="secret")
        self.assertEqual(run_script.call_args.kwargs["password"], "secret")

    def test_kernel_maintenance_relocks_the_verified_kernel_with_sudo(self) -> None:
        executor = Mock()
        executor.exec_sudo_in_dir.return_value = 0
        with TemporaryDirectory() as temp_dir:
            release_lock = Path(temp_dir) / "lock_linux_release.sh"
            release_lock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            with (
                patch("app.core.gpu_driver_runner.GPU_DRIVER_RELEASE_LOCK_SCRIPT", release_lock),
                patch("app.core.gpu_driver_runner._log"),
            ):
                _run_rocky_release_lock(executor, "/tmp/task-kernel", "task-kernel", Mock(), password="secret")

        command = executor.exec_sudo_in_dir.call_args.args[0]
        self.assertIn("umask 022", command)
        self.assertNotIn("sudo -n bash", command)
        self.assertNotIn("secret", command)
        self.assertEqual(executor.exec_sudo_in_dir.call_args.kwargs["password"], "secret")

    def test_failed_rocky_boot_restores_default_using_saved_sudo_credential(self) -> None:
        executor = Mock()
        executor.exec_sudo.return_value = (0, "", "")
        _restore_default_kernel(
            executor, "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", password="secret",
        )
        command = executor.exec_sudo.call_args.args[0]
        self.assertIn("grubby --set-default", command)
        self.assertIn("grub2-editenv \"$dir/grubenv\" set saved_entry=", command)
        self.assertNotIn("secret", command)
        self.assertEqual(executor.exec_sudo.call_args.kwargs["password"], "secret")

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
