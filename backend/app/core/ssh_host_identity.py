import base64
import hashlib

import paramiko


class SSHHostIdentityError(Exception):
    pass


def fingerprint_for_host_key(host_key: paramiko.PKey) -> str:
    """Return the OpenSSH-style SHA256 fingerprint for a remote host key."""
    digest = hashlib.sha256(host_key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def remote_host_identity(client: paramiko.SSHClient) -> tuple[str, str]:
    transport = client.get_transport()
    if transport is None:
        raise SSHHostIdentityError("SSH host identity is unavailable")
    host_key = transport.get_remote_server_key()
    return fingerprint_for_host_key(host_key), host_key.get_name()


def require_expected_host_identity(client: paramiko.SSHClient, expected_fingerprint: str | None) -> tuple[str, str]:
    fingerprint, algorithm = remote_host_identity(client)
    if expected_fingerprint and fingerprint != expected_fingerprint:
        raise SSHHostIdentityError(
            f"SSH host identity changed: expected {expected_fingerprint}, got {fingerprint}"
        )
    return fingerprint, algorithm
