import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.artifact_collector import collect_artifacts
from app.core.ssh_executor import SSHExecutor


class _FakeSession:
    def add(self, _item) -> None:
        pass

    def commit(self) -> None:
        pass


class ArtifactCollectorSftpTests(unittest.TestCase):
    def test_collection_opens_sftp_lazily(self) -> None:
        executor = SSHExecutor()
        executor.client = MagicMock()
        sftp = executor.client.open_sftp.return_value
        sftp.listdir_attr.return_value = [
            MagicMock(filename="report.txt", st_mode=stat.S_IFREG | 0o644),
        ]
        sftp.get.side_effect = lambda _remote, local: Path(local).write_text("PASS", encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.core.artifact_collector.ARTIFACTS_DIR",
            Path(temp_dir),
        ):
            downloaded = collect_artifacts(
                _FakeSession(),
                "task-test",
                "/remote/work",
                executor,
            )

            self.assertEqual(downloaded, ["report.txt"])
            self.assertEqual(
                (Path(temp_dir) / "task-test" / "report.txt").read_text(encoding="utf-8"),
                "PASS",
            )
        executor.client.open_sftp.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
