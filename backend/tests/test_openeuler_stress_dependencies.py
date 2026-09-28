import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "stress"
SCRIPTS = {
    "cpu_mem_stress_report.sh": ("stress-ng",),
    "disk_stress_report.sh": ("fio", "iostat"),
}


def _function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[start:end]


class OpenEulerStressDependencyTests(unittest.TestCase):
    def _run_install(
        self, script_name: str, *, installed: bool, install_succeeds: bool,
        install_provides: bool = True,
    ):
        source = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os_release = root / "os-release"
            os_release.write_text('ID=openeuler\nVERSION_ID="24.03"\n', encoding="utf-8")
            (root / "python3").touch()
            if installed:
                for name in (*SCRIPTS[script_name], "openpyxl"):
                    (root / name).touch()

            detect = _function(source, "is_openeuler").replace(
                "/etc/os-release", str(os_release)
            ) if "is_openeuler() {" in source else "is_openeuler() { return 1; }"
            harness = "\n".join(
                (
                    'DNF_MINRATE=51200 DNF_TIMEOUT=30 DNF_RETRIES=2 DNF_INSTALL_ATTEMPTS=1',
                    detect,
                    _function(source, "install_deps"),
                    'id() { printf "0\\n"; }',
                    'command() { [ "$1" = "-v" ] || return 1; [ -e "$TEST_ROOT/$2" ]; }',
                    'python3() { [ -e "$TEST_ROOT/openpyxl" ]; }',
                    'dnf_install_with_retry() { printf "dnf:%s\\n" "$*"; '
                    '[ "$INSTALL_SUCCEEDS" = 1 ] || return 1; '
                    '[ "$INSTALL_PROVIDES" = 1 ] || return 0; '
                    'for package in "$@"; do '
                    'case "$package" in '
                    'stress-ng|fio|sysstat|python3-openpyxl) '
                    '[ "$package" = sysstat ] && package=iostat; '
                    '[ "$package" = python3-openpyxl ] && package=openpyxl; '
                    'touch "$TEST_ROOT/$package";; '
                    'esac; done; }',
                    'ensure_epel_repo() { echo EPEL_CALLED; return 1; }',
                    'repair_centos_linux_8_repos() { echo CENTOS_CALLED; return 1; }',
                    'apt() { echo APT_CALLED; return 1; }',
                    "install_deps",
                )
            )
            env = os.environ.copy()
            env["TEST_ROOT"] = str(root)
            env["INSTALL_SUCCEEDS"] = "1" if install_succeeds else "0"
            env["INSTALL_PROVIDES"] = "1" if install_provides else "0"
            return subprocess.run(
                ["bash", "-c", harness],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

    def test_openeuler_installed_dependencies_skip_package_manager(self) -> None:
        for script_name in SCRIPTS:
            with self.subTest(script=script_name):
                result = self._run_install(script_name, installed=True, install_succeeds=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Dependencies already installed", result.stdout)
                self.assertNotIn("dnf:", result.stdout)

    def test_openeuler_missing_dependencies_install_from_configured_repos(self) -> None:
        for script_name in SCRIPTS:
            with self.subTest(script=script_name):
                result = self._run_install(script_name, installed=False, install_succeeds=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("dnf:", result.stdout)
                self.assertNotIn("EPEL_CALLED", result.stdout)
                self.assertNotIn("CENTOS_CALLED", result.stdout)

    def test_openeuler_dnf_success_without_dependency_still_fails(self) -> None:
        for script_name in SCRIPTS:
            with self.subTest(script=script_name):
                result = self._run_install(
                    script_name, installed=False, install_succeeds=True,
                    install_provides=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Dependency unavailable after install", result.stdout)

    def test_openeuler_install_failure_stops_before_stress(self) -> None:
        for script_name in SCRIPTS:
            with self.subTest(script=script_name):
                result = self._run_install(script_name, installed=False, install_succeeds=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Dependency installation failed", result.stdout)
                self.assertNotIn("EPEL_CALLED", result.stdout)
                self.assertNotIn("CENTOS_CALLED", result.stdout)


if __name__ == "__main__":
    unittest.main()
