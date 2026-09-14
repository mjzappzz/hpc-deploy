import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.tasks import _require_server_ssh_identity_confirmed
from app.api.tasks import _extreme_preflight
from app.api.tasks import _extreme_preflight_snapshot
from app.api.tasks import _task_resource_domains
from app.api.tasks import _resource_conflicts
from app.api.tasks import _read_remote_extreme_preflight_checks
from app.api.tasks import run_task
from app.schemas.task import ExtremePreflightResponse, ExtremePreflightCheck, TaskRunRequest
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
        self.assertTrue({"ssh_identity", "gpu", "connectivity"}.issubset(
            {check.key for check in result.checks if check.status == "blocked"}
        ))

    @patch("app.api.tasks._read_remote_extreme_preflight_checks", return_value=[])
    def test_extreme_preflight_snapshot_is_json_safe_and_keeps_each_check(self, _remote_checks: MagicMock) -> None:
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

    def test_resource_domains_keep_disk_and_read_only_tasks_out_of_gpu_cpu_mutex(self) -> None:
        self.assertEqual(_task_resource_domains("stress", "extreme_stress_report.sh"), {"gpu", "cpu_mem"})
        self.assertEqual(_task_resource_domains("stress", "gpu_stress_report.sh"), {"gpu"})
        self.assertEqual(_task_resource_domains("stress", "cpu_mem_stress_report.sh"), {"cpu_mem"})
        self.assertEqual(_task_resource_domains("stress", "disk_stress_report.sh"), set())
        self.assertEqual(_task_resource_domains("script", "collect_inventory.sh"), set())

    def test_resource_conflicts_only_returns_overlapping_domains(self) -> None:
        gpu_task = SimpleNamespace(
            task_id="task-gpu", task_type="stress", file_name="gpu_stress_report.sh",
            status="RUNNING", batch_id=None,
        )
        disk_task = SimpleNamespace(
            task_id="task-disk", task_type="stress", file_name="disk_stress_report.sh",
            status="RUNNING", batch_id=None,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [gpu_task, disk_task]

        conflicts = _resource_conflicts(db, server_id=1, target_domains={"gpu", "cpu_mem"})

        self.assertEqual([(task.task_id, domains) for task, domains in conflicts], [("task-gpu", {"gpu"})])

    @patch("app.api.tasks.SSHExecutor")
    def test_remote_preflight_blocks_low_memory_and_warns_when_temperature_is_unavailable(
        self,
        executor_class: MagicMock,
    ) -> None:
        executor_class.return_value.exec_capture.return_value = (
            0,
            "mem_total_mb=32768\nmem_available_mb=1000\nremote_free_kb=2097152\nstress_ng=1\npython3=1\nnvidia_smi=1\ngpu_temperature=0",
            "",
        )
        server = SimpleNamespace(
            host="10.0.0.1", port=22, username="root", key_path="/tmp/key", password=None,
            ssh_host_fingerprint="SHA256:confirmed",
        )

        checks = _read_remote_extreme_preflight_checks(server)
        by_key = {check.key: check for check in checks}

        self.assertEqual(by_key["connectivity"].status, "pass")
        self.assertEqual(by_key["memory_headroom"].status, "blocked")
        self.assertEqual(by_key["remote_storage"].status, "pass")
        self.assertEqual(by_key["temperature_monitor"].status, "warning")

    @patch("app.api.tasks._extreme_preflight")
    def test_extreme_submission_runs_fresh_server_side_preflight(self, preflight: MagicMock) -> None:
        preflight.return_value = ExtremePreflightResponse(
            server_id=1,
            can_submit=False,
            checks=[ExtremePreflightCheck(key="memory_headroom", status="blocked", message="insufficient")],
        )
        server = SimpleNamespace(id=1, ssh_host_fingerprint="SHA256:confirmed")
        db = MagicMock()
        db.get.return_value = server

        with self.assertRaises(HTTPException) as raised:
            run_task(
                TaskRunRequest(
                    server_id=1,
                    task_type="stress",
                    file_path="scripts/stress/extreme_stress_report.sh",
                    params={"duration_seconds": 60, "extreme_mode": True},
                ),
                MagicMock(),
                db,
            )

        self.assertEqual(raised.exception.status_code, 409)
        preflight.assert_called_once_with(server, db)
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
