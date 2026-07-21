import unittest

from app.core.cuda_toolkit_runner import (
    build_cuda_toolkit_install_script,
    cuda_toolkit_environment_commands,
    resolve_cuda_toolkit_os_profile,
    should_skip_existing_cuda_toolkit,
)


class CudaToolkitRunnerTests(unittest.TestCase):
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
