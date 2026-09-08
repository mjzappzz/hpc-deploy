import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.servers import archive_server, create_server, restore_server, update_server
from app.db.database import Base
from app.models.server import Server, is_server_archived
from app.schemas.server import ServerCreate, ServerUpdate


class ServerDuplicateHostTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.db.close()

    @patch("app.api.servers.write_audit_log")
    @patch("app.api.servers._probe_server")
    def test_create_rejects_an_existing_host(self, _probe_server, _write_audit_log) -> None:
        create_server(ServerCreate(name="first", host="10.0.0.1", username="root"), self.db)

        with self.assertRaises(HTTPException) as error:
            create_server(ServerCreate(name="second", host="10.0.0.1", username="root"), self.db)

        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("IP 地址已录入", error.exception.detail)

    @patch("app.api.servers.write_audit_log")
    @patch("app.api.servers._probe_server")
    def test_update_rejects_another_servers_host(self, _probe_server, _write_audit_log) -> None:
        first = create_server(ServerCreate(name="first", host="10.0.0.1", username="root"), self.db)
        second = create_server(ServerCreate(name="second", host="10.0.0.2", username="root"), self.db)

        with self.assertRaises(HTTPException) as error:
            update_server(second.id, ServerUpdate(host=first.host), self.db)

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.get(Server, second.id).host, "10.0.0.2")

    @patch("app.api.servers.write_audit_log")
    @patch("app.api.servers._probe_server")
    def test_create_allows_reuse_of_an_archived_servers_host(self, _probe_server, _write_audit_log) -> None:
        archived = create_server(ServerCreate(name="retired", host="10.0.0.1", username="root"), self.db)
        archive_server(archived.id, self.db)

        replacement = create_server(ServerCreate(name="replacement", host="10.0.0.1", username="root"), self.db)

        self.assertEqual(replacement.host, "10.0.0.1")
        self.assertTrue(is_server_archived(self.db.get(Server, archived.id)))

    @patch("app.api.servers.write_audit_log")
    @patch("app.api.servers._probe_server")
    def test_restore_rejects_when_an_active_server_now_uses_its_host(self, _probe_server, _write_audit_log) -> None:
        archived = create_server(ServerCreate(name="retired", host="10.0.0.1", username="root"), self.db)
        archive_server(archived.id, self.db)
        create_server(ServerCreate(name="replacement", host="10.0.0.1", username="root"), self.db)

        with self.assertRaises(HTTPException) as error:
            restore_server(archived.id, self.db)

        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(is_server_archived(self.db.get(Server, archived.id)))


if __name__ == "__main__":
    unittest.main()
