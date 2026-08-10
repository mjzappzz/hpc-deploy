import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.ops_commands import create_ops_command, delete_ops_command, list_ops_commands, update_ops_command
from app.db.database import Base
from app.models.audit_log import AuditLog
from app.models.ops_command import OpsCommand
from app.schemas.ops_command import OpsCommandCreate, OpsCommandUpdate


class OpsCommandModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_command_record_keeps_a_short_title_and_multiline_content(self) -> None:
        command = OpsCommand(
            title="Ubuntu 开启 root SSH 登录",
            content="sudo passwd root\n\nsudo systemctl restart ssh\n",
        )
        self.db.add(command)
        self.db.commit()

        saved = self.db.query(OpsCommand).one()
        self.assertEqual(saved.title, "Ubuntu 开启 root SSH 登录")
        self.assertIn("sudo systemctl restart ssh", saved.content)
        self.assertIsNotNone(saved.created_at)
        self.assertIsNotNone(saved.updated_at)

    def test_command_crud_audits_title_without_auditing_command_content(self) -> None:
        created = create_ops_command(
            OpsCommandCreate(title="检查 ECC", content="sudo journalctl -k | grep -Ei 'edac|uecc'"),
            self.db,
            "admin",
        )
        updated = update_ops_command(
            created.id,
            OpsCommandUpdate(title="检查 ECC / UE", content="sudo journalctl -k | grep -Ei 'edac|uecc|uncorrected'"),
            self.db,
            "admin",
        )

        self.assertEqual([item.id for item in list_ops_commands(self.db)], [created.id])
        self.assertEqual(updated.title, "检查 ECC / UE")
        audit_messages = [entry.detail_json or "" for entry in self.db.query(AuditLog).all()]
        self.assertTrue(audit_messages)
        self.assertFalse(any("journalctl" in detail for detail in audit_messages))

        delete_ops_command(created.id, self.db, "admin")
        self.assertEqual(list_ops_commands(self.db), [])

    def test_command_content_keeps_bold_markup_but_removes_executable_html(self) -> None:
        command = create_ops_command(
            OpsCommandCreate(
                title="富文本命令",
                content='<p>执行 <strong>sudo reboot</strong></p><img src=x onerror=alert(1)><script>alert(1)</script>',
            ),
            self.db,
            "admin",
        )

        self.assertEqual(command.content, '<p>执行 <strong>sudo reboot</strong></p>')


if __name__ == "__main__":
    unittest.main()
