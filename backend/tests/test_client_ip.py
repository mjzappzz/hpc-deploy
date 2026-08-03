import unittest

from app.core.audit import write_audit_log
from app.core.client_ip import reset_client_ip, resolve_client_ip, set_client_ip


class _AuditDb:
    def __init__(self) -> None:
        self.entry = None

    def add(self, entry: object) -> None:
        self.entry = entry

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class ClientIpTests(unittest.TestCase):
    def test_uses_valid_nginx_real_ip_for_loopback_proxy(self) -> None:
        self.assertEqual(
            resolve_client_ip({"x-real-ip": "192.0.2.18"}, "127.0.0.1"),
            "192.0.2.18",
        )

    def test_ignores_forwarded_ip_from_non_proxy_client(self) -> None:
        self.assertEqual(
            resolve_client_ip({"x-real-ip": "192.0.2.18"}, "198.51.100.31"),
            "198.51.100.31",
        )

    def test_falls_back_to_proxy_peer_for_invalid_forwarded_ip(self) -> None:
        self.assertEqual(
            resolve_client_ip({"x-real-ip": "not-an-ip"}, "127.0.0.1"),
            "127.0.0.1",
        )

    def test_audit_log_uses_request_client_ip_when_not_explicitly_provided(self) -> None:
        db = _AuditDb()
        token = set_client_ip("2001:db8::9")
        try:
            write_audit_log(db, action="task.create", target_type="task", status="success")
        finally:
            reset_client_ip(token)

        self.assertEqual(db.entry.client_ip, "2001:db8::9")
