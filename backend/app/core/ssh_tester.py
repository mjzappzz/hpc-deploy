from pathlib import Path
from socket import timeout as SocketTimeout

import paramiko

from app.core.ssh_detector import DEFAULT_DETECT_TIMEOUT


class SSHTestError(Exception):
    pass


def test_ssh_connection(
    *,
    host: str,
    port: int,
    username: str,
    key_path: str | None,
    password: str | None = None,
    timeout: int = DEFAULT_DETECT_TIMEOUT,
) -> dict[str, str]:
    connect_kwargs: dict[str, object] = {}
    if password:
        connect_kwargs["password"] = password
    else:
        if not key_path:
            raise SSHTestError("SSH key_path is not configured")
        key_file = Path(key_path).expanduser()
        if not key_file.is_file():
            raise SSHTestError(f"SSH key file not found: {key_path}")
        connect_kwargs["key_filename"] = str(key_file)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
            **connect_kwargs,
        )
        hostname = _run_fixed_command(client, "hostname", timeout)
        uname = _run_fixed_command(client, "uname -a", timeout)
        return {"hostname": hostname, "uname": uname}
    except (SocketTimeout, TimeoutError) as exc:
        raise SSHTestError(f"SSH connection timed out after {timeout}s") from exc
    except paramiko.AuthenticationException as exc:
        raise SSHTestError("SSH authentication failed") from exc
    except paramiko.SSHException as exc:
        raise SSHTestError(f"SSH connection failed: {exc}") from exc
    except OSError as exc:
        raise SSHTestError(f"SSH network error: {exc}") from exc
    finally:
        client.close()


def _run_fixed_command(client: paramiko.SSHClient, command: str, timeout: int) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error = stderr.read().decode("utf-8", errors="replace").strip()
    if exit_code != 0:
        raise SSHTestError(f"command failed: {command}: {error or output}")
    return output
