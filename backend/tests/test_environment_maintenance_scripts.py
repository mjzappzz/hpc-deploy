from pathlib import Path
import os
import re
import subprocess
import unittest

from app.core.script_library import extract_content_version


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "mpi"


def _script(name: str) -> str:
    path = SCRIPTS_DIR / name
    assert path.is_file(), f"missing managed script: {path}"
    subprocess.run(["bash", "-n", str(path)], check=True)
    return path.read_text(encoding="utf-8")


def _shell_function(content: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n",
        content,
    )
    assert match is not None, f"missing shell function: {name}"
    return match.group(0)


class EnvironmentMaintenanceScriptTests(unittest.TestCase):
    def test_oneapi_installer_is_idempotent(self) -> None:
        content = _script("install_oneapi_2022.sh")

        self.assertIn('SCRIPT_VERSION="1.1.0"', content)
        self.assertIn("basekit_is_ready", content)
        self.assertIn("hpckit_is_ready", content)
        self.assertIn("BaseKit 目标组件已安装，跳过安装", content)
        self.assertIn("HPCKit 目标组件已安装，跳过安装", content)
        self.assertIn("verify_required_commands", content)

    def test_aocc_openmpi_installer_is_idempotent(self) -> None:
        content = _script("install_openmpi_4.1.6_aocc_aocl.sh")

        self.assertIn('SCRIPT_VERSION="1.1.0"', content)
        self.assertIn("aocc_is_ready", content)
        self.assertIn("aocl_is_ready", content)
        self.assertIn("openmpi_is_ready", content)
        self.assertIn("AOCC 已安装，跳过安装", content)
        self.assertIn("AOCL 已安装，跳过安装", content)
        self.assertIn("OpenMPI 4.1.6 已安装，跳过编译", content)
        self.assertIn("verify_amd_installation", content)

    def test_lock_linux_release_has_safe_scope(self) -> None:
        content = _script("lock_linux_release.sh")

        self.assertIn('SCRIPT_VERSION="1.7.5"', content)
        self.assertIn('[[ "$VERSION_ID" =~ ^9\\.[0-9]+$ ]]', content)
        self.assertIn('select_rocky_repo_root', content)
        self.assertIn('"--setopt=reposdir=${probe_root}"', content)
        self.assertIn("command -v timeout", content)
        self.assertIn("timeout --signal=TERM --kill-after=10s 90s", content)
        self.assertIn("--enablerepo=epel", content)
        self.assertIn("makecache --refresh", content)
        self.assertIn('repo_root="$(select_rocky_repo_root)"', content)
        self.assertLess(
            content.index('repo_root="$(select_rocky_repo_root)"'),
            content.index('mkdir -p "${BACKUP_DIR}"'),
        )
        self.assertIn('printf \'%s\\n\' "$VERSION_ID" > /etc/dnf/vars/releasever', content)
        self.assertIn('rocky-${VERSION_ID}-hpcdeploy.repo', content)
        self.assertNotIn('rocky-9.4-hpcdeploy.repo', content)
        self.assertIn('${BASHPID}', content)
        self.assertIn('mkdir "${BACKUP_DIR}"', content)
        self.assertIn("rollback_rocky_config", content)
        self.assertIn("ROCKY_MUTATION_STARTED=1", content)
        self.assertIn("自动回滚未完整通过校验", content)
        self.assertIn("verify_repo_backup_restored", content)
        self.assertIn("collect_running_kernel_lock_specs", content)
        self.assertIn('rpm -q "kernel-core-${running_kernel}"', content)
        self.assertIn("kernel-modules-extra", content)
        self.assertIn("kernel-devel", content)
        self.assertIn("kernel-headers", content)
        self.assertIn("verify_kernel_versionlocks", content)
        self.assertIn("versionlock.list", content)
        self.assertIn("collect_ubuntu_kernel_hold_packages", content)
        self.assertIn("linux-image-${running_kernel}", content)
        self.assertIn("linux-modules-${running_kernel}", content)
        self.assertIn("linux-modules-extra-${running_kernel}", content)
        self.assertIn("linux-headers-${running_kernel}", content)
        self.assertIn("generic|image-generic|headers-generic", content)
        self.assertIn("virtual|image-virtual|headers-virtual", content)
        self.assertIn("oem|image-oem|headers-oem", content)
        self.assertIn('apt-mark hold "${UBUNTU_KERNEL_HOLD_PACKAGES[@]}"', content)
        self.assertIn('APT_LOCK_MAX_WAIT_SECONDS=900', content)
        self.assertIn('APT_LOCK_POLL_SECONDS=5', content)
        self.assertIn('APT_STALL_MAX_SECONDS=10', content)
        self.assertIn('APT_MIN_DOWNLOAD_BYTES_PER_SECOND=524288', content)
        apt_lock_wait = _shell_function(content, "wait_for_apt_dpkg_unlock")
        self.assertIn('fuser "${APT_LOCK_FILES[@]}"', apt_lock_wait)
        self.assertIn('sleep "$APT_LOCK_POLL_SECONDS"', apt_lock_wait)
        self.assertIn('锁持续占用超过', apt_lock_wait)
        self.assertIn('is_stalled_automatic_apt_update', apt_lock_wait)
        self.assertIn('recover_stalled_automatic_apt_update', apt_lock_wait)
        automatic_update_check = _shell_function(content, "is_stalled_automatic_apt_update")
        self.assertIn('/system.slice/apt-daily-upgrade.service', automatic_update_check)
        self.assertIn('/proc/${pid}/cgroup', automatic_update_check)
        recovery = _shell_function(content, "recover_stalled_automatic_apt_update")
        self.assertIn('systemctl stop --no-block apt-daily-upgrade.service', recovery)
        self.assertIn('systemctl kill --kill-who=all --signal=SIGTERM apt-daily-upgrade.service', recovery)
        self.assertNotIn('SIGKILL', recovery)
        self.assertIn('dpkg --configure -a', recovery)
        self.assertIn('不终止人工 apt/dpkg 或 cloud-init', recovery)
        self.assertGreaterEqual(content.count('wait_for_apt_dpkg_unlock'), 3)
        self.assertNotIn('rm -f /var/lib/dpkg/lock', content)
        self.assertIn("verify_ubuntu_kernel_holds", content)
        self.assertIn("repo_file_has_managed_id", content)
        self.assertIn("awk -v target=", content)
        self.assertIn('[[ "$repo_id_count" == "1" ]]', content)
        self.assertIn("for required_repo in baseos appstream crb epel", content)
        self.assertIn('"--enablerepo=epel" makecache --refresh', content)
        self.assertIn('VERSION_ID" != "22.04"', content)
        self.assertIn('VERSION_ID" != "24.04"', content)
        self.assertIn("当前版本：Ubuntu ${VERSION_ID:-unknown}", content)
        self.assertIn("Prompt=never", content)
        self.assertIn("rocky-vault/${VERSION_ID}", content)
        self.assertIn("download.rockylinux.org/pub/rocky/${VERSION_ID}", content)
        self.assertIn("download.rockylinux.org/vault/rocky/${VERSION_ID}", content)
        self.assertNotIn("download.rockylinux.org/pub/rocky/9.8", content)
        self.assertIn("versionlock add", content)
        self.assertIn("mirrors.aliyun.com/epel/9/Everything/$basearch/", content)
        self.assertIn("RPM-GPG-KEY-EPEL-9", content)
        self.assertIn('dnf "${dnf_core_args[@]}" versionlock add', content)
        self.assertNotIn("dnf update", content)
        self.assertNotIn("yum update", content)
        self.assertNotIn("sudo ", content)
        self.assertEqual(extract_content_version(content), "v1.7.5")

    def test_lock_linux_release_accepts_held_installed_ubuntu_packages(self) -> None:
        content = _script("lock_linux_release.sh")
        function = _shell_function(content, "ubuntu_package_is_installed")
        command = (
            f"{function}\n"
            "dpkg-query() {\n"
            "    [[ \"$#\" -eq 3 && \"$1\" == \"-W\" "
            "&& \"$2\" == '-f=${db:Status-Abbrev}' "
            "&& \"$3\" == \"linux-image-test\" ]] || return 97\n"
            "    printf '%s' \"$MOCK_DPKG_STATUS\"\n"
            "    return \"${MOCK_DPKG_EXIT:-0}\"\n"
            "}\n"
            'ubuntu_package_is_installed "linux-image-test"\n'
        )

        for status in ("ii ", "hi "):
            with self.subTest(status=status):
                result = subprocess.run(
                    ["bash", "-c", command],
                    env={**os.environ, "MOCK_DPKG_STATUS": status},
                    check=False,
                )
                self.assertEqual(result.returncode, 0)

        for status in ("rc ", "un ", "pi ", "ri ", "ui ", "iiR", "hiR", "ii rc "):
            with self.subTest(status=status):
                result = subprocess.run(
                    ["bash", "-c", command],
                    env={**os.environ, "MOCK_DPKG_STATUS": status},
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)

        query_failure = subprocess.run(
            ["bash", "-c", command],
            env={
                **os.environ,
                "MOCK_DPKG_STATUS": "ii ",
                "MOCK_DPKG_EXIT": "1",
            },
            check=False,
        )
        self.assertNotEqual(query_failure.returncode, 0)

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
