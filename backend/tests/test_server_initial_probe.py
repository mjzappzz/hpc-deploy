import unittest
import time
from datetime import datetime
from unittest.mock import patch

from app.api.servers import _detect_server_info_with_deadline, _probe_server, create_server, server_ready_for_public_key_deploy
from app.core.ssh_detector import ServerDetectError, ServerDetectTimeout
from app.models.server import Server
from app.schemas.server import ServerCreate


class _FakeSession:
    def get(self, _model, _key):
        return None

    def add(self, _item) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, _item) -> None:
        pass


class ServerInitialProbeTests(unittest.TestCase):
    def test_probe_preserves_last_verified_gpu_inventory_while_driver_is_recovering(self) -> None:
        server = Server(
            id=3,
            name="restarting-gpu-server",
            host="10.0.0.4",
            port=22,
            username="root",
            auth_type="password",
            password="secret",
            status="offline",
            last_check_at=datetime(2026, 8, 5, 8, 46),
            os_info="Ubuntu 22.04 LTS",
            gpu_status="driver_ok",
            gpu_info="NVIDIA GeForce RTX 4090 x8 / Driver 590.48.01 / CUDA 12.8",
        )
        db = _FakeSession()
        raw_result = {
            "os_release": 'PRETTY_NAME="Ubuntu 24.04 LTS"',
            "uname": "Linux restarting-gpu-server",
            "cpu_info": "Model name: CPU\nCPU(s): 16",
            "memory_info": "Mem: 32Gi 1Gi 31Gi",
            "disk_info": "Filesystem Size Used Avail Use% Mounted on\n/dev/sda 100G 10G 90G 10% /",
            "gpu_info": "01:00.0 VGA compatible controller: NVIDIA Corporation AD102 [GeForce RTX 4090] (rev a1)\n---GPU-SPLIT---\n__NVIDIA_SMI_FAILED__\n---CUDA-SPLIT---\n__NVCC_NOT_FOUND__",
        }

        with patch("app.api.servers.detect_server_info", return_value=(raw_result, {})), \
             patch("app.api.servers.write_audit_log"):
            result = _probe_server(db, server)

        self.assertTrue(result.success)
        self.assertEqual(server.status, "online")
        self.assertEqual(server.last_check_at, datetime(2026, 8, 5, 8, 46))
        self.assertEqual(server.os_info, "Ubuntu 22.04 LTS")
        self.assertEqual(server.gpu_status, "driver_ok")
        self.assertEqual(server.gpu_info, "NVIDIA GeForce RTX 4090 x8 / Driver 590.48.01 / CUDA 12.8")

    def test_probe_deadline_covers_entire_detector_call(self) -> None:
        with patch("app.api.servers.detect_server_info", side_effect=lambda **_kwargs: time.sleep(0.2)):
            with self.assertRaises(ServerDetectTimeout):
                _detect_server_info_with_deadline(deadline_seconds=0.01)

    def test_failed_probe_updates_last_check_time(self) -> None:
        previous_check = datetime(2026, 7, 1)
        server = Server(
            id=1,
            name="offline-server",
            host="10.0.0.2",
            port=22,
            username="root",
            auth_type="password",
            password="secret",
            status="offline",
            last_check_at=previous_check,
        )
        db = _FakeSession()

        with patch("app.api.servers.detect_server_info", side_effect=ServerDetectError("unreachable")), \
             patch("app.api.servers.write_audit_log"):
            result = _probe_server(db, server)

        self.assertFalse(result.success)
        self.assertGreater(server.last_check_at, previous_check)

    def test_probe_command_timeout_preserves_online_status(self) -> None:
        previous_check = datetime(2026, 7, 1)
        server = Server(
            id=2,
            name="slow-server",
            host="10.0.0.3",
            port=22,
            username="root",
            auth_type="password",
            password="secret",
            status="online",
            last_check_at=previous_check,
        )
        db = _FakeSession()

        with patch("app.api.servers.detect_server_info", side_effect=ServerDetectTimeout("probe timed out")), \
             patch("app.api.servers.write_audit_log"):
            result = _probe_server(db, server)

        self.assertFalse(result.success)
        self.assertEqual(server.status, "online")
        self.assertGreater(server.last_check_at, previous_check)
        self.assertEqual(server.last_error, "probe timed out")

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
