import os
from pathlib import Path
import subprocess
import tempfile
import unittest


STRESS_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "stress"
STRESS_SCRIPTS = (
    "gpu_stress_report.sh",
    "cpu_mem_stress_report.sh",
    "disk_stress_report.sh",
)


class StressDependencyRetryPolicyTests(unittest.TestCase):
    def test_rpm_install_retries_failed_downloads_and_refreshes_metadata(self) -> None:
        for script_name in STRESS_SCRIPTS:
            with self.subTest(script=script_name), tempfile.TemporaryDirectory() as temp_dir:
                source = (STRESS_SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
                function_source = source[
                    source.index("rpm_package_manager()") : source.index("\nensure_epel_repo()")
                ]
                temp_path = Path(temp_dir)
                counter_path = temp_path / "counter"
                args_path = temp_path / "args"
                fake_dnf = temp_path / "dnf"
                fake_dnf.write_text(
                    """#!/bin/sh
count=0
if [ -f "$HPCDEPLOY_TEST_COUNTER" ]; then
    count="$(cat "$HPCDEPLOY_TEST_COUNTER")"
fi
count=$((count + 1))
printf '%s' "$count" > "$HPCDEPLOY_TEST_COUNTER"
printf '%s\n' "$*" >> "$HPCDEPLOY_TEST_ARGS"
[ "$count" -ge 3 ]
""",
                    encoding="utf-8",
                )
                fake_dnf.chmod(0o755)
                harness = f"""
DNF_MINRATE=51200
DNF_TIMEOUT=30
DNF_RETRIES=2
DNF_INSTALL_ATTEMPTS=3
{function_source}
sleep() {{ :; }}
dnf_install_with_retry stress-ng
"""
                env = os.environ.copy()
                env["PATH"] = f"{temp_dir}:{env['PATH']}"
                env["HPCDEPLOY_TEST_COUNTER"] = str(counter_path)
                env["HPCDEPLOY_TEST_ARGS"] = str(args_path)

                result = subprocess.run(
                    ["bash", "-c", harness],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(counter_path.read_text(encoding="utf-8"), "3")
                attempts = args_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(attempts), 3)
                self.assertNotIn("--refresh", attempts[0])
                self.assertIn("--refresh", attempts[1])
                self.assertIn("--refresh", attempts[2])

    def test_rpm_installs_have_bounded_low_speed_retry_policy(self) -> None:
        for script_name in STRESS_SCRIPTS:
            with self.subTest(script=script_name):
                source = (STRESS_SCRIPTS_DIR / script_name).read_text(encoding="utf-8")

                self.assertIn('HPCDEPLOY_DNF_MINRATE:-51200', source)
                self.assertIn('HPCDEPLOY_DNF_TIMEOUT:-30', source)
                self.assertIn('HPCDEPLOY_DNF_RETRIES:-2', source)
                self.assertIn('HPCDEPLOY_DNF_INSTALL_ATTEMPTS:-3', source)
                self.assertIn('--setopt="minrate=${DNF_MINRATE}"', source)
                self.assertIn('--setopt="timeout=${DNF_TIMEOUT}"', source)
                self.assertIn('--setopt="retries=${DNF_RETRIES}"', source)
                self.assertIn('dnf_install_with_retry', source)
                self.assertIn('refresh_args=(--refresh)', source)
                self.assertIn('Dependency install attempt ${attempt}/${DNF_INSTALL_ATTEMPTS}', source)

    def test_rpm_installs_request_only_missing_packages(self) -> None:
        for script_name in STRESS_SCRIPTS:
            with self.subTest(script=script_name):
                source = (STRESS_SCRIPTS_DIR / script_name).read_text(encoding="utf-8")

                self.assertIn('rpm_packages=()', source)
                self.assertIn('if [ "${#rpm_packages[@]}" -gt 0 ]', source)
                self.assertNotIn('yum install -y stress-ng python3 python3-pip', source)
                self.assertNotIn('yum install -y gcc gcc-c++ make wget unzip', source)

    def test_final_rpm_install_failure_is_not_ignored(self) -> None:
        for script_name in STRESS_SCRIPTS:
            with self.subTest(script=script_name):
                source = (STRESS_SCRIPTS_DIR / script_name).read_text(encoding="utf-8")

                self.assertIn('[ERROR] Dependency installation failed after', source)
                self.assertNotIn('yum install -y epel-release || true', source)
                self.assertIn('ensure_epel_repo || return 1', source)
                self.assertIn('install_deps || exit 1', source)


if __name__ == "__main__":
    unittest.main()
