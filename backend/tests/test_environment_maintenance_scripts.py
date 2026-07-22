from pathlib import Path
import subprocess
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "mpi"


def _script(name: str) -> str:
    path = SCRIPTS_DIR / name
    assert path.is_file(), f"missing managed script: {path}"
    subprocess.run(["bash", "-n", str(path)], check=True)
    return path.read_text(encoding="utf-8")


class EnvironmentMaintenanceScriptTests(unittest.TestCase):
    def test_lock_linux_release_has_safe_scope(self) -> None:
        content = _script("lock_linux_release.sh")

        self.assertIn('"9.4")', content)
        self.assertIn('VERSION_ID" != "22.04"', content)
        self.assertIn('VERSION_ID" != "24.04"', content)
        self.assertIn("当前系统版本为 Rocky Linux ${VERSION_ID:-unknown}，非 9.4，无需锁定系统版本", content)
        self.assertIn("当前版本：Ubuntu ${VERSION_ID:-unknown}", content)
        self.assertIn("Prompt=never", content)
        self.assertIn("rocky-vault/9.4", content)
        self.assertNotIn("download.rockylinux.org/pub/rocky/9.8", content)
        self.assertIn("printf '9.4\\n' > /etc/dnf/vars/releasever", content)
        self.assertIn("versionlock add", content)
        self.assertNotIn("dnf update", content)
        self.assertNotIn("yum update", content)
        self.assertNotIn("sudo ", content)

    def test_disable_linux_lock_sleep_avoids_session_disruption(self) -> None:
        content = _script("disable_linux_lock_sleep.sh")

        self.assertIn(
            "systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target",
            content,
        )
        self.assertIn("IdleAction=ignore", content)
        self.assertIn("org/gnome/desktop/screensaver/lock-enabled", content)
        self.assertNotIn("systemctl restart systemd-logind", content)
        self.assertNotIn("sudo ", content)


if __name__ == "__main__":
    unittest.main()
