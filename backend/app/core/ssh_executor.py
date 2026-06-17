from pathlib import Path
from socket import timeout as SocketTimeout
from time import monotonic, sleep
from typing import Callable

import paramiko


class SSHExecutorError(Exception):
    pass


class SSHCommandTimeoutError(SSHExecutorError):
    def __init__(self, command: str, timeout_seconds: int) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        super().__init__(f"command timed out after {timeout_seconds} seconds")


class SSHExecutor:
    def __init__(self, *, timeout: int = 15) -> None:
        self.timeout = timeout
        self.client: paramiko.SSHClient | None = None
        self.sftp: paramiko.SFTPClient | None = None

    def connect(self, *, host: str, port: int, username: str, key_path: str | None) -> None:
        if not key_path:
            raise SSHExecutorError("SSH key_path is not configured")

        key_file = Path(key_path).expanduser()
        if not key_file.is_file():
            raise SSHExecutorError(f"SSH key file not found: {key_path}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=username,
                key_filename=str(key_file),
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            self.client = client
            self.sftp = client.open_sftp()
        except (SocketTimeout, TimeoutError) as exc:
            client.close()
            raise SSHExecutorError(f"SSH connection timed out after {self.timeout}s") from exc
        except paramiko.AuthenticationException as exc:
            client.close()
            raise SSHExecutorError("SSH authentication failed") from exc
        except paramiko.SSHException as exc:
            client.close()
            raise SSHExecutorError(f"SSH connection failed: {exc}") from exc
        except OSError as exc:
            client.close()
            raise SSHExecutorError(f"SSH network error: {exc}") from exc

    def mkdir_p(self, remote_dir: str) -> None:
        self.exec_simple(f"mkdir -p {shell_quote(remote_dir)}")

    def get_remote_home(self) -> str:
        output = self.exec_simple("printf '%s' \"$HOME\"")
        if not output.startswith("/"):
            raise SSHExecutorError("remote HOME is invalid")
        return output

    def upload_file(self, local_path: str, remote_path: str) -> None:
        if self.sftp is None:
            raise SSHExecutorError("SFTP session is not connected")
        try:
            self.sftp.put(local_path, remote_path)
        except OSError as exc:
            raise SSHExecutorError(f"upload failed: {exc}") from exc

    def chmod(self, remote_path: str, mode: int) -> None:
        octal_mode = format(mode, "o")
        self.exec_simple(f"chmod {octal_mode} {shell_quote(remote_path)}")

    def exec_command_in_dir(
        self,
        command: str,
        cwd: str,
        *,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
        on_stderr_line: Callable[[str], None] | None = None,
    ) -> int:
        if self.client is None:
            raise SSHExecutorError("SSH client is not connected")

        wrapped = f"cd {shell_quote(cwd)} && {command}"
        try:
            _stdin, stdout, stderr = self.client.exec_command(wrapped, timeout=self.timeout)
        except (SocketTimeout, TimeoutError) as exc:
            raise SSHExecutorError(f"remote command failed to start: {command}") from exc
        except paramiko.SSHException as exc:
            raise SSHExecutorError(f"remote command failed to start: {exc}") from exc

        channel = stdout.channel
        deadline = monotonic() + timeout_seconds
        stdout_buffer = ""
        stderr_buffer = ""

        while True:
            stdout_buffer = _drain_channel_lines(
                recv_ready=channel.recv_ready,
                receiver=channel.recv,
                buffer=stdout_buffer,
                on_line=on_stdout_line,
            )
            stderr_buffer = _drain_channel_lines(
                recv_ready=channel.recv_stderr_ready,
                receiver=channel.recv_stderr,
                buffer=stderr_buffer,
                on_line=on_stderr_line,
            )

            if channel.exit_status_ready():
                break

            if monotonic() > deadline:
                channel.close()
                raise SSHCommandTimeoutError(command, timeout_seconds)

            sleep(0.2)

        while channel.recv_ready():
            stdout_buffer = _drain_channel_lines(
                recv_ready=channel.recv_ready,
                receiver=channel.recv,
                buffer=stdout_buffer,
                on_line=on_stdout_line,
            )
        while channel.recv_stderr_ready():
            stderr_buffer = _drain_channel_lines(
                recv_ready=channel.recv_stderr_ready,
                receiver=channel.recv_stderr,
                buffer=stderr_buffer,
                on_line=on_stderr_line,
            )

        _flush_remaining_line(stdout_buffer, on_stdout_line)
        _flush_remaining_line(stderr_buffer, on_stderr_line)
        return channel.recv_exit_status()

    def exec_simple(self, command: str) -> str:
        if self.client is None:
            raise SSHExecutorError("SSH client is not connected")
        try:
            _stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()
        except (SocketTimeout, TimeoutError) as exc:
            raise SSHExecutorError(f"remote command timed out: {command}") from exc
        except paramiko.SSHException as exc:
            raise SSHExecutorError(f"remote command failed to start: {exc}") from exc

        if exit_code != 0:
            raise SSHExecutorError(f"command failed: {error or output or command}")
        return output

    def exec_capture(self, command: str, *, timeout_seconds: int) -> tuple[int, str, str]:
        if self.client is None:
            raise SSHExecutorError("SSH client is not connected")
        try:
            _stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout_seconds)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()
        except (SocketTimeout, TimeoutError) as exc:
            raise SSHCommandTimeoutError(command, timeout_seconds) from exc
        except paramiko.SSHException as exc:
            raise SSHExecutorError(f"remote command failed to start: {exc}") from exc
        return exit_code, output, error

    def close(self) -> None:
        if self.sftp is not None:
            self.sftp.close()
            self.sftp = None
        if self.client is not None:
            self.client.close()
            self.client = None


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _drain_channel_lines(
    *,
    recv_ready: Callable[[], bool],
    receiver: Callable[[int], bytes],
    buffer: str,
    on_line: Callable[[str], None] | None,
) -> str:
    while recv_ready():
        chunk = receiver(4096).decode("utf-8", errors="replace")
        if not chunk:
            break
        buffer += chunk
        lines = buffer.splitlines(keepends=True)
        buffer = ""
        for line in lines:
            if line.endswith("\n") or line.endswith("\r"):
                clean_line = line.rstrip("\r\n")
                if clean_line and on_line is not None:
                    on_line(clean_line)
            else:
                buffer = line
    return buffer


def _flush_remaining_line(buffer: str, on_line: Callable[[str], None] | None) -> None:
    clean_line = buffer.rstrip("\r\n")
    if clean_line and on_line is not None:
        on_line(clean_line)
