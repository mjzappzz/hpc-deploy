import unittest
from pathlib import Path

from fastapi import HTTPException

from app.api.tasks import _get_server_or_400
from app.models.server import ARCHIVED_SERVER_TAG, Server


class _ServerSession:
    def __init__(self, server: Server | None) -> None:
        self.server = server

    def get(self, _model, _server_id: int) -> Server | None:
        return self.server


class ArchivedServerGuardTests(unittest.TestCase):
    def test_archive_and_restore_routes_require_admin_token(self) -> None:
        source = Path("backend/app/api/servers.py").read_text(encoding="utf-8")

        self.assertIn('def archive_server(server_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin_token))', source)
        self.assertIn('def restore_server(server_id: int, db: Session = Depends(get_db), _: str = Depends(require_admin_token))', source)

    def test_general_server_update_cannot_switch_archive_tag(self) -> None:
        source = Path("backend/app/api/servers.py").read_text(encoding="utf-8")

        self.assertIn('detail="请使用归档操作"', source)
        self.assertIn('detail="已归档服务器仅可通过恢复管理操作解除冻结"', source)

    def test_task_creation_guard_rejects_archived_server(self) -> None:
        server = Server(id=1, name="sold", host="10.0.0.1", username="root", tags_json=f'["{ARCHIVED_SERVER_TAG}"]')

        with self.assertRaises(HTTPException) as raised:
            _get_server_or_400(_ServerSession(server), 1)

        self.assertEqual(raised.exception.status_code, 409)

    def test_task_creation_guard_allows_managed_server(self) -> None:
        server = Server(id=1, name="managed", host="10.0.0.1", username="root", tags_json='["待压测"]')

        self.assertIs(_get_server_or_400(_ServerSession(server), 1), server)


if __name__ == "__main__":
    unittest.main()
