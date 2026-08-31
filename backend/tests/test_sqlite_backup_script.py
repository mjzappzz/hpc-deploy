from pathlib import Path
import os
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "backup_sqlite.sh"


class SqliteBackupScriptTests(unittest.TestCase):
    def test_keeps_only_the_seven_newest_successful_backups(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source_database = temporary_root / "source.db"
            backup_directory = temporary_root / "backups"
            backup_directory.mkdir()

            with sqlite3.connect(source_database) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.execute("INSERT INTO sample VALUES ('backup source')")

            for day in range(1, 8):
                backup_path = backup_directory / f"hpc_control_panel_2026010{day}-023000.db"
                with sqlite3.connect(backup_path) as connection:
                    connection.execute("CREATE TABLE sample (value TEXT)")

            environment = os.environ | {"HPCDEPLOY_DB_PATH": str(source_database)}
            result = subprocess.run(
                ["bash", str(SCRIPT), str(backup_directory)],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            backups = sorted(backup_directory.glob("hpc_control_panel_*.db"))
            self.assertEqual(len(backups), 7)
            self.assertFalse((backup_directory / "hpc_control_panel_20260101-023000.db").exists())
            backup_values = []
            for backup_path in backups:
                with sqlite3.connect(backup_path) as connection:
                    row = connection.execute("SELECT value FROM sample").fetchone()
                if row:
                    backup_values.append(row[0])
            self.assertIn("backup source", backup_values)
