import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.tasks import _require_server_ssh_identity_confirmed
from app.api.tasks import _extreme_preflight
from app.api.tasks import _extreme_preflight_snapshot
from app.models.server import Server


class ServerSshIdentityModelTests(unittest.TestCase):
    def test_server_record_exposes_persisted_ssh_identity_fields(self) -> None:
        columns = Server.__table__.columns

        self.assertIn("ssh_host_fingerprint", columns)
        self.assertIn("ssh_host_key_algorithm", columns)
        self.assertIn("ssh_host_key_confirmed_at", columns)
        self.assertIn("key_auth_verified_at", columns)

    def test_unconfirmed_server_is_rejected_before_remote_task_creation(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _require_server_ssh_identity_confirmed(SimpleNamespace(ssh_host_fingerprint=None))

        self.assertEqual(raised.exception.status_code, 409)

    def test_extreme_preflight_blocks_an_unconfirmed_or_gpu_unready_server(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        server = SimpleNamespace(id=1, ssh_host_fingerprint=None, status="online", gpu_status="none")

        result = _extreme_preflight(server, db)

        self.assertFalse(result.can_submit)
        self.assertEqual({check.key for check in result.checks if check.status == "blocked"}, {"ssh_identity", "gpu"})

    def test_extreme_preflight_snapshot_is_json_safe_and_keeps_each_check(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _extreme_preflight(
            SimpleNamespace(id=1, ssh_host_fingerprint="SHA256:confirmed", status="online", gpu_status="driver_ok"),
            db,
        )

        snapshot = _extreme_preflight_snapshot(result)

        self.assertTrue(snapshot["can_submit"])
        self.assertIsInstance(snapshot["checked_at"], str)
        self.assertEqual([item["key"] for item in snapshot["checks"]], [check.key for check in result.checks])
        self.assertNotIn("password", str(snapshot))


if __name__ == "__main__":
    unittest.main()
