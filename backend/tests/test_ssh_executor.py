import unittest
from unittest.mock import MagicMock, patch

from app.core.ssh_executor import SSHExecutor


class SSHExecutorSftpTests(unittest.TestCase):
    @patch("app.core.ssh_executor.paramiko.SSHClient")
    def test_connect_does_not_require_sftp(self, ssh_client_cls: MagicMock) -> None:
        client = ssh_client_cls.return_value
        client.open_sftp.side_effect = EOFError("SFTP subsystem is disabled")

        executor = SSHExecutor()
        executor.connect(
            host="10.0.0.1",
            port=22,
            username="root",
            key_path=None,
            password="secret",
        )

        client.connect.assert_called_once()
        client.open_sftp.assert_not_called()
        self.assertIs(executor.client, client)

    @patch("app.core.ssh_executor.paramiko.SSHClient")
    def test_upload_opens_sftp_lazily(self, ssh_client_cls: MagicMock) -> None:
        client = ssh_client_cls.return_value
        sftp = client.open_sftp.return_value
        executor = SSHExecutor()
        executor.connect(
            host="10.0.0.1",
            port=22,
            username="root",
            key_path=None,
            password="secret",
        )

        executor.upload_file("/tmp/local", "/tmp/remote")

        client.open_sftp.assert_called_once_with()
        sftp.put.assert_called_once_with("/tmp/local", "/tmp/remote")


if __name__ == "__main__":
    unittest.main()
