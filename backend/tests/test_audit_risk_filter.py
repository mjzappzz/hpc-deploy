import unittest

from app.api.audit import HIGH_RISK_AUDIT_ACTIONS


class AuditRiskFilterTests(unittest.TestCase):
    def test_high_risk_actions_include_destructive_and_configuration_changes(self) -> None:
        expected = {
            "server.delete",
            "server.deploy_public_key",
            "task.cancel",
            "task.delete",
            "script.upload",
            "script.delete",
            "cleanup.local_artifacts.delete",
            "cleanup.remote.delete",
            "settings.update",
            "settings.change_password",
        }
        self.assertTrue(expected.issubset(HIGH_RISK_AUDIT_ACTIONS))

    def test_routine_task_execution_is_not_high_risk(self) -> None:
        self.assertNotIn("task.create", HIGH_RISK_AUDIT_ACTIONS)
        self.assertNotIn("task.diagnose", HIGH_RISK_AUDIT_ACTIONS)
