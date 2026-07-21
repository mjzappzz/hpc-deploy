import unittest

from pydantic import ValidationError

from app.schemas.server import ServerCreate, ServerUpdate


class ServerTagTests(unittest.TestCase):
    def test_new_servers_default_to_pending_stress_tag(self) -> None:
        payload = ServerCreate(name="test", host="127.0.0.1", username="root")
        self.assertEqual(payload.tags, ["待压测"])

    def test_server_tags_are_limited_to_one_fixed_option(self) -> None:
        payload = ServerUpdate(tags=["待压测"])
        self.assertEqual(payload.tags, ["待压测"])
        with self.assertRaises(ValidationError):
            ServerUpdate(tags=[])
        with self.assertRaises(ValidationError):
            ServerUpdate(tags=["待压测", "测试机"])
        with self.assertRaises(ValidationError):
            ServerUpdate(tags=["临时机器"])
