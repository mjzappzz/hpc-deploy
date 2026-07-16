import unittest
from datetime import datetime
from unittest.mock import patch

from app.api.servers import create_server, server_ready_for_public_key_deploy
from app.models.server import Server
from app.schemas.server import ServerCreate


class _FakeSession:
    def add(self, _item) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, _item) -> None:
        pass


class ServerInitialProbeTests(unittest.TestCase):
    def test_create_server_runs_initial_probe(self) -> None:
        payload = ServerCreate(
            name="new-server",
            host="10.0.0.1",
            username="root",
            auth_type="password",
            password="secret",
        )
        db = _FakeSession()

        def probe_server(_db, server) -> None:
            server.status = "online"
            server.last_check_at = datetime.utcnow()
            server.os_info = "Ubuntu 24.04"

        with patch("app.api.servers.write_audit_log"), patch("app.api.servers._probe_server", side_effect=probe_server) as probe:
            server = create_server(payload, db)

        probe.assert_called_once_with(db, server)
        self.assertEqual(server.status, "online")
        self.assertEqual(server.os_info, "Ubuntu 24.04")

    def test_public_key_deploy_requires_successful_initial_probe(self) -> None:
        server = Server(status="online", last_check_at=datetime.utcnow())
        self.assertTrue(server_ready_for_public_key_deploy(server))

        server.last_check_at = None
        self.assertFalse(server_ready_for_public_key_deploy(server))

        server.last_check_at = datetime.utcnow()
        server.status = "offline"
        self.assertFalse(server_ready_for_public_key_deploy(server))


if __name__ == "__main__":
    unittest.main()
