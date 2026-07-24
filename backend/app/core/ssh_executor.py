import base64
from pathlib import Path
from socket import timeout as SocketTimeout
from time import monotonic, sleep
from typing import Callable

import paramiko


REMOTE_HOME_MARKER = "__HPCDEPLOY_HOME__="
COMMAND_OUTPUT_BEGIN = "__HPCDEPLOY_OUTPUT_BEGIN__"
COMMAND_OUTPUT_END = "__HPCDEPLOY_OUTPUT_END__"


def _wrap_command(command: str) -> str:
    return (
        f"printf '%s\\n' '{COMMAND_OUTPUT_BEGIN}'; "
        f"( {command} ); hpcdeploy_rc=$?; "
        f"printf '\\n%s\\n' '{COMMAND_OUTPUT_END}'; exit $hpcdeploy_rc"
    )


def _extract_command_output(output: str) -> str:
    begin = output.find(COMMAND_OUTPUT_BEGIN)
    end = output.rfind(COMMAND_OUTPUT_END)
    if begin < 0 or end < begin:
        return output.strip()
    return output[begin + len(COMMAND_OUTPUT_BEGIN):end].strip()


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
        self._connect_params: dict[str, object] | None = None

    def connect(
        self,
        *,
        host: str,
        port: int,
        username: str,
        key_path: str | None,
        password: str | None = None,
    ) -> None:
        connect_kwargs: dict[str, object] = {}
        if password:
            connect_kwargs["password"] = password
        else:
            if not key_path:
                raise SSHExecutorError("SSH key_path is not configured")
            key_file = Path(key_path).expanduser()
            if not key_file.is_file():
                raise SSHExecutorError(f"SSH key file not found: {key_path}")
            connect_kwargs["key_filename"] = str(key_file)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=username,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
                **connect_kwargs,
            )
            self.client = client
            self._connect_params = {
                "host": host,
                "port": port,
                "username": username,
                "key_path": key_path,
                "password": password,
            }
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

    def reconnect(self) -> None:
        """Close existing connection and reconnect using stored params.

        Raises SSHExecutorError if no stored connection params or reconnect fails.
        """
        if self._connect_params is None:
            raise SSHExecutorError("no stored connection params, cannot reconnect")
        self.close()
        self.connect(**self._connect_params)

    def mkdir_p(self, remote_dir: str) -> None:
        self.exec_simple(f"mkdir -p {shell_quote(remote_dir)}")

    def get_remote_home(self) -> str:
        output = self.exec_simple(f"printf '\\n{REMOTE_HOME_MARKER}%s\\n' \"$HOME\"")
        marked_lines = [line for line in output.splitlines() if line.startswith(REMOTE_HOME_MARKER)]
        remote_home = marked_lines[-1][len(REMOTE_HOME_MARKER):].strip() if marked_lines else ""
        if not remote_home.startswith("/") or any(char in remote_home for char in ("\x00", "\r", "\n")):
            raise SSHExecutorError("remote HOME is invalid")
        return remote_home

    def upload_file(self, local_path: str, remote_path: str) -> None:
        try:
            sftp = self.get_sftp()
            sftp.put(local_path, remote_path)
            return
        except (EOFError, OSError, paramiko.SFTPError, paramiko.SSHException, SSHExecutorError):
            self._upload_file_via_ssh(local_path, remote_path)

    def _upload_file_via_ssh(self, local_path: str, remote_path: str) -> None:
        """Upload through an exec channel when the SFTP protocol is unavailable."""
        if self.client is None:
            raise SSHExecutorError("SSH client is not connected")
        command = f"cat > {shell_quote(remote_path)}"
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
            with Path(local_path).open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    stdin.write(chunk)
            stdin.channel.shutdown_write()
            exit_code = stdout.channel.recv_exit_status()
            error = stderr.read().decode("utf-8", errors="replace").strip()
        except (EOFError, OSError, SocketTimeout, TimeoutError, paramiko.SSHException) as exc:
            raise SSHExecutorError(f"upload failed via SSH stream: {exc}") from exc
        if exit_code != 0:
            raise SSHExecutorError(f"upload failed via SSH stream: {error or command}")

    def list_remote_files(self, remote_dir: str) -> list[str]:
        command = (
            f"test -d {shell_quote(remote_dir)} || exit 3; "
            f"find {shell_quote(remote_dir)} -maxdepth 1 -type f "
            "-printf '%f\\n' 2>/dev/null || true"
        )
        exit_code, output, error = self.exec_capture(command, timeout_seconds=self.timeout)
        if exit_code != 0:
            raise SSHExecutorError(f"failed to list remote directory: {error or output}")
        return [line for line in output.splitlines() if line]

    def download_file(self, remote_path: str, local_path: str) -> None:
        try:
            self.get_sftp().get(remote_path, local_path)
            return
        except (EOFError, OSError, paramiko.SFTPError, paramiko.SSHException, SSHExecutorError):
            pass
        exit_code, output, error = self.exec_capture(
            f"base64 -w 0 -- {shell_quote(remote_path)}",
            timeout_seconds=max(self.timeout, 60),
        )
        if exit_code != 0:
            raise SSHExecutorError(f"download failed via SSH stream: {error or output}")
        try:
            Path(local_path).write_bytes(base64.b64decode(output, validate=True))
        except (OSError, ValueError) as exc:
            raise SSHExecutorError(f"download failed via SSH stream: {exc}") from exc

    def get_sftp(self) -> paramiko.SFTPClient:
        if self.client is None:
            raise SSHExecutorError("SFTP session is not connected")
        if self.sftp is None:
            try:
                self.sftp = self.client.open_sftp()
            except (EOFError, OSError, paramiko.SFTPError, paramiko.SSHException) as exc:
                raise SSHExecutorError(f"SFTP session failed: {exc}") from exc
        return self.sftp

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
        on_tick: Callable[[], bool] | None = None,
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

            # on_tick 回调：每 ~5s 调用一次，返回 True 时关闭 channel 提前结束
            if on_tick:
                _tick_cnt = getattr(on_tick, '_tick_cnt', 0) + 1
                on_tick._tick_cnt = _tick_cnt
                if _tick_cnt % 25 == 0:
                    try:
                        if on_tick():
                            channel.close()
                            raise SSHCommandTimeoutError(command, timeout_seconds)
                    except Exception:
                        pass

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
            _stdin, stdout, stderr = self.client.exec_command(_wrap_command(command), timeout=self.timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()
        except (SocketTimeout, TimeoutError) as exc:
            raise SSHExecutorError(f"remote command timed out: {command}") from exc
        except paramiko.SSHException as exc:
            raise SSHExecutorError(f"remote command failed to start: {exc}") from exc

        if exit_code != 0:
            raise SSHExecutorError(f"command failed: {error or output or command}")
        return _extract_command_output(output)

    def exec_capture(self, command: str, *, timeout_seconds: int) -> tuple[int, str, str]:
        if self.client is None:
            raise SSHExecutorError("SSH client is not connected")
        try:
            _stdin, stdout, stderr = self.client.exec_command(_wrap_command(command), timeout=timeout_seconds)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()
        except (SocketTimeout, TimeoutError) as exc:
            raise SSHCommandTimeoutError(command, timeout_seconds) from exc
        except paramiko.SSHException as exc:
            raise SSHExecutorError(f"remote command failed to start: {exc}") from exc
        return exit_code, _extract_command_output(output), error

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
