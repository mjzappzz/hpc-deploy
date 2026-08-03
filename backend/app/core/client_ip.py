from collections.abc import Mapping
from contextvars import ContextVar, Token
from ipaddress import ip_address


_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
_LOOPBACK_PROXY_HOSTS = frozenset({"127.0.0.1", "::1"})


def resolve_client_ip(headers: Mapping[str, str], peer_host: str | None) -> str | None:
    """Return a validated client IP, trusting proxy headers only from local Nginx."""
    if peer_host in _LOOPBACK_PROXY_HOSTS:
        forwarded_ip = headers.get("x-real-ip", "").strip()
        if _is_ip_address(forwarded_ip):
            return forwarded_ip
    return peer_host if _is_ip_address(peer_host) else None


def set_client_ip(client_ip: str | None) -> Token[str | None]:
    return _client_ip.set(client_ip)


def reset_client_ip(token: Token[str | None]) -> None:
    _client_ip.reset(token)


def get_client_ip() -> str | None:
    return _client_ip.get()


def _is_ip_address(value: str | None) -> bool:
    if not value:
        return False
    try:
        ip_address(value)
    except ValueError:
        return False
    return True
