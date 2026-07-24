import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import paramiko

from app.core.ssh_executor import (
    COMMAND_OUTPUT_BEGIN,
    COMMAND_OUTPUT_END,
    SSHExecutor,
    SSHExecutorError,
    _extract_command_output,
)


class SSHExecutorRemoteHomeTests(unittest.TestCase):
    def test_get_remote_home_ignores_shell_startup_output(self) -> None:
        executor = SSHExecutor()
        executor.exec_simple = MagicMock(
            return_value=(
                ":: initializing oneAPI environment ...\n"
                ":: oneAPI environment initialized ::\n"
                "__HPCDEPLOY_HOME__=/root"
            )
        )

        self.assertEqual(executor.get_remote_home(), "/root")

    def test_get_remote_home_rejects_relative_marker_value(self) -> None:
        executor = SSHExecutor()
        executor.exec_simple = MagicMock(return_value="__HPCDEPLOY_HOME__=root")

        with self.assertRaisesRegex(SSHExecutorError, "remote HOME is invalid"):
            executor.get_remote_home()


class SSHExecutorCommandOutputTests(unittest.TestCase):
    def test_extract_command_output_ignores_shell_startup_banner(self) -> None:
        output = (
            ":: initializing oneAPI environment ...\n"
            f"{COMMAND_OUTPUT_BEGIN}\n"
            "82069\n"
            f"{COMMAND_OUTPUT_END}\n"
        )

        self.assertEqual(_extract_command_output(output), "82069")


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

    def test_upload_falls_back_to_ssh_stream_when_sftp_is_unavailable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            local_path = Path(tmp_dir) / "payload.bin"
            local_path.write_bytes(b"\x00payload\n")

            executor = SSHExecutor()
            executor.client = MagicMock()
            executor.get_sftp = MagicMock(side_effect=paramiko.SFTPError("Garbage packet received"))
            stdin = MagicMock()
            stdout = MagicMock()
            stderr = MagicMock()
            stdout.channel.recv_exit_status.return_value = 0
            stderr.read.return_value = b""
            executor.client.exec_command.return_value = (stdin, stdout, stderr)

            executor.upload_file(str(local_path), "/tmp/remote payload.bin")

            stdin.write.assert_called_once_with(b"\x00payload\n")
            stdin.channel.shutdown_write.assert_called_once_with()
            executor.client.exec_command.assert_called_once_with(
                "cat > '/tmp/remote payload.bin'",
                timeout=executor.timeout,
            )


if __name__ == "__main__":
    unittest.main()
