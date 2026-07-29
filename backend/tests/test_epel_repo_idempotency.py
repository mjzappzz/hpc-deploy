from pathlib import Path
import unittest

from app.core.gpu_driver_runner import build_rocky9_pre_reboot_script


BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOCK_SCRIPT = BACKEND_ROOT / "scripts" / "mpi" / "lock_linux_release.sh"
STRESS_SCRIPTS = (
    BACKEND_ROOT / "scripts" / "stress" / "gpu_stress_report.sh",
    BACKEND_ROOT / "scripts" / "stress" / "cpu_mem_stress_report.sh",
    BACKEND_ROOT / "scripts" / "stress" / "disk_stress_report.sh",
)


class EpelRepoIdempotencyTests(unittest.TestCase):
    def test_release_lock_uses_standard_epel_repo_filename(self) -> None:
        source = LOCK_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("/etc/yum.repos.d/epel.repo", source)
        self.assertNotIn("/etc/yum.repos.d/epel-9-hpcdeploy.repo", source)
        self.assertIn("dnf versionlock list", source)
        self.assertIn("--disablerepo=*", source)
        self.assertIn("--setopt=timeout=20", source)

    def test_driver_install_skips_epel_release_when_epel_is_enabled(self) -> None:
        source = build_rocky9_pre_reboot_script()

        self.assertIn("epel_repo_enabled", source)
        self.assertIn("EPEL repository already enabled", source)

    def test_stress_scripts_skip_epel_release_when_epel_is_enabled(self) -> None:
        for script in STRESS_SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                self.assertIn("epel_repo_enabled", source)
                self.assertIn("EPEL repository already enabled", source)


if __name__ == "__main__":
    unittest.main()
