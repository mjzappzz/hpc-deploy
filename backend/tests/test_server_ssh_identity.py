import unittest

from app.models.server import Server


class ServerSshIdentityModelTests(unittest.TestCase):
    def test_server_record_exposes_persisted_ssh_identity_fields(self) -> None:
        columns = Server.__table__.columns

        self.assertIn("ssh_host_fingerprint", columns)
        self.assertIn("ssh_host_key_algorithm", columns)
        self.assertIn("ssh_host_key_confirmed_at", columns)
        self.assertIn("key_auth_verified_at", columns)


if __name__ == "__main__":
    unittest.main()
