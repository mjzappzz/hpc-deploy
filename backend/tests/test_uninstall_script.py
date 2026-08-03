from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "deploy" / "scripts" / "uninstall_hpcdeploy.sh"


class UninstallScriptTests(unittest.TestCase):
    def test_has_safe_default_and_valid_shell_syntax(self) -> None:
        self.assertTrue(SCRIPT.is_file())

        syntax = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        dry_run = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("dry-run", dry_run.stdout)
        self.assertNotIn("运行数据", dry_run.stdout.split("将删除：", 1)[-1])

    def test_requires_force_for_data_or_secret_purge(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT), "--purge-runtime-data"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--force", result.stderr)
