import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.core.cuda_toolkit_runner import (
    build_cuda_toolkit_install_script,
    cuda_toolkit_environment_commands,
    resolve_cuda_toolkit_os_profile,
    should_skip_existing_cuda_toolkit,
)


class CudaToolkitRunnerTests(unittest.TestCase):
    def test_rocky_download_survives_external_default_cache_cleanup(self) -> None:
        for force_install in (False, True):
            with self.subTest(force_install=force_install), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = root / "task with spaces"
                task_dir.mkdir()
                bin_dir = root / "bin"
                bin_dir.mkdir()
                global_cache = root / "global-cache"
                global_cache.mkdir()
                sentinel = global_cache / "unrelated.rpm"
                sentinel.write_text("other task's package")
                command_log = root / "dnf-commands.jsonl"
                # Run the actual generated preparation/install phases with harmless
                # executables; no root access, network or system packages are used.
                for name, source in {
                    "sudo": '#!/bin/bash\nif [[ "${1:-}" == -n ]]; then shift; fi\nexec "$@"\n',
                    "nvidia-smi": "#!/bin/bash\nexit 0\n",
                    "dnf": '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
default_cache = Path(os.environ["TEST_DEFAULT_CACHE"])
cache = default_cache
for arg in args:
    if arg.startswith("--setopt=cachedir="):
        cache = Path(arg.split("=", 2)[2])
with open(os.environ["TEST_COMMAND_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "cache": str(cache)}) + "\\n")
if "clean" in args:
    for package in cache.glob("*.rpm"):
        package.unlink()
if "cuda-toolkit-12-8" in args:
    cache.mkdir(parents=True, exist_ok=True)
    package = cache / "cuda-cccl.rpm"
    package.write_text("downloaded")
    # Model a concurrent plain `dnf clean all` after the download lock
    # is released, immediately before signature verification.
    for cached_package in default_cache.glob("*.rpm"):
        cached_package.unlink()
    if not package.exists():
        sys.exit("downloaded RPM disappeared before signature verification")
''',
                }.items():
                    executable = bin_dir / name
                    executable.write_text(source)
                    executable.chmod(0o755)
                script = build_cuda_toolkit_install_script(
                    "rocky9", "12.8", force_install=force_install
                ).split("echo '========== [4/4]")[0]
                installer = task_dir / "cuda-toolkit-install.sh"
                installer.write_text(script)
                result = subprocess.run(
                    ["bash", str(installer)],
                    cwd=root,  # Cache must follow the installer, not the caller's cwd.
                    env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                         "TEST_DEFAULT_CACHE": str(global_cache),
                         "TEST_COMMAND_LOG": str(command_log)},
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(sentinel.exists(), "external cleanup must actually run")
                self.assertTrue((task_dir / "dnf-cache" / "cuda-cccl.rpm").exists())
                commands = [json.loads(line) for line in command_log.read_text().splitlines()]
                self.assertTrue(all(c["cache"] == str(task_dir / "dnf-cache") for c in commands))
                self.assertFalse(any("clean" in c["args"] for c in commands))
                self.assertIn("reinstall" if force_install else "install", commands[-1]["args"])
                self.assertIn("--refresh", commands[-1]["args"])

    def test_generated_installers_have_valid_shell_syntax(self) -> None:
        for profile in ("rocky9", "ubuntu2204", "ubuntu2404"):
            for force_install in (False, True):
                with self.subTest(profile=profile, force_install=force_install):
                    result = subprocess.run(
                        ["bash", "-n"], input=build_cuda_toolkit_install_script(
                            profile, "12.8", force_install=force_install
                        ), capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_supported_os_profiles_are_rocky9_ubuntu22_and_ubuntu24(self) -> None:
        self.assertEqual(resolve_cuda_toolkit_os_profile("Rocky Linux 9.4 (Blue Onyx)"), "rocky9")
        self.assertEqual(resolve_cuda_toolkit_os_profile("Ubuntu 22.04.5 LTS"), "ubuntu2204")
        self.assertEqual(resolve_cuda_toolkit_os_profile("Ubuntu 24.04.2 LTS"), "ubuntu2404")
        with self.assertRaisesRegex(ValueError, "unsupported CUDA Toolkit"):
            resolve_cuda_toolkit_os_profile("Ubuntu 20.04.6 LTS")

    def test_rocky_script_installs_versioned_toolkit_without_driver(self) -> None:
        script = build_cuda_toolkit_install_script("rocky9", "12.8", force_install=False)
        self.assertIn("cuda-rhel9.repo", script)
        self.assertIn("cuda-toolkit-12-8", script)
        self.assertNotIn("dnf -y install cuda\n", script)
        self.assertIn("/etc/profile.d/cuda-12.8.sh", script)
        self.assertIn("/usr/local/cuda-12.8/bin/nvcc --version", script)

    def test_ubuntu22_uses_its_own_repository_and_versioned_package(self) -> None:
        script = build_cuda_toolkit_install_script("ubuntu2204", "12.8", force_install=True)
        self.assertIn("cuda/repos/ubuntu2204/x86_64", script)
        self.assertIn("cuda-toolkit-12-8", script)
        self.assertIn("apt-get -y install --reinstall cuda-toolkit-12-8", script)

    def test_ubuntu_keyring_download_avoids_http2_and_retries_transient_failures(self) -> None:
        script = build_cuda_toolkit_install_script("ubuntu2204", "12.8", force_install=False)

        self.assertIn("curl --http1.1 --fail --show-error --location", script)
        self.assertIn("--retry 3 --retry-delay 2 --retry-all-errors", script)
        self.assertIn("--connect-timeout 20 --max-time 120", script)

    def test_ubuntu_installer_waits_for_apt_locks_and_recovers_stalled_automatic_updates(self) -> None:
        script = build_cuda_toolkit_install_script("ubuntu2404", "12.8", force_install=False)

        self.assertIn("APT_LOCK_MAX_WAIT_SECONDS=900", script)
        self.assertIn("APT_STALL_MAX_SECONDS=10", script)
        self.assertIn("wait_for_apt_dpkg_unlock", script)
        self.assertIn("recover_stalled_automatic_apt_update", script)
        self.assertIn("lslocks -n -o PID,PATH", script)
        self.assertIn("apt-daily-upgrade.service", script)
        self.assertGreaterEqual(script.count("wait_for_apt_dpkg_unlock"), 4)
        self.assertNotIn("rm -f /var/lib/dpkg/lock", script)

    def test_existing_version_is_only_skipped_without_force_flag(self) -> None:
        self.assertTrue(should_skip_existing_cuda_toolkit(nvcc_available=True, force_install=False))
        self.assertFalse(should_skip_existing_cuda_toolkit(nvcc_available=True, force_install=True))
        self.assertFalse(should_skip_existing_cuda_toolkit(nvcc_available=False, force_install=False))

    def test_cuda_13_uses_the_matching_versioned_toolkit_package(self) -> None:
        script = build_cuda_toolkit_install_script("ubuntu2404", "13.0", force_install=False)
        self.assertIn("cuda-toolkit-13-0", script)
        self.assertIn("/usr/local/cuda-13.0/bin/nvcc --version", script)

    def test_environment_commands_are_generated_for_the_installed_version(self) -> None:
        commands = cuda_toolkit_environment_commands("12.9")
        self.assertIn("export PATH=/usr/local/cuda-12.9/bin:$PATH", commands)
        self.assertIn("export CUDA_PATH=/usr/local/cuda-12.9", commands)

    def test_cuda_runner_recovers_running_detached_tasks_after_restart(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app" / "core" / "cuda_toolkit_runner.py"
        ).read_text(encoding="utf-8")

        self.assertIn('Task.status.in_(("PENDING", "RUNNING"))', source)
        self.assertIn("_build_detached_remote_execution_command(", source)
        self.assertIn("startup recovery: reattached detached CUDA Toolkit monitor", source)
        self.assertIn("CUDA Toolkit recovery SSH unavailable; task remains RUNNING", source)
        self.assertIn("_schedule_cuda_recovery_retry(task_id)", source)
