import unittest

from pydantic import ValidationError

from app.models.server import ARCHIVED_SERVER_TAG, Server, is_server_archived
from app.schemas.server import ServerCreate, ServerUpdate


class ServerTagTests(unittest.TestCase):
    def test_server_host_is_trimmed_for_create_and_update(self) -> None:
        created = ServerCreate(name="test", host=" 10.87.86.163 ", username="root")
        updated = ServerUpdate(host=" 10.87.86.163 ")

        self.assertEqual(created.host, "10.87.86.163")
        self.assertEqual(updated.host, "10.87.86.163")

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

    def test_archived_server_tag_is_a_supported_fixed_tag(self) -> None:
        payload = ServerUpdate(tags=[ARCHIVED_SERVER_TAG])
        self.assertEqual(payload.tags, [ARCHIVED_SERVER_TAG])

    def test_archived_server_is_identified_by_its_fixed_tag(self) -> None:
        self.assertTrue(is_server_archived(Server(tags_json=f'["{ARCHIVED_SERVER_TAG}"]')))
        self.assertFalse(is_server_archived(Server(tags_json='["待压测"]')))
