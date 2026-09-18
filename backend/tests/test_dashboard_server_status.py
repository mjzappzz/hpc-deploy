import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api.dashboard import _count_server_statuses


class DashboardServerStatusTests(unittest.TestCase):
    def test_unavailable_managed_servers_are_reported_as_offline(self) -> None:
        now = datetime.utcnow()
        stats = _count_server_statuses([
            SimpleNamespace(status="online", last_check_at=now),
            SimpleNamespace(status="offline"),
            SimpleNamespace(status="unknown"),
            SimpleNamespace(status=None),
            SimpleNamespace(status="online", last_check_at=now - timedelta(hours=1, minutes=1)),
        ])

        self.assertEqual(stats, {"total": 5, "online": 1, "offline": 4, "unknown": 0})

    def test_archived_servers_are_excluded_from_dashboard_statuses(self) -> None:
        stats = _count_server_statuses([
            SimpleNamespace(status="online", last_check_at=datetime.utcnow(), tags=["已归档服务器"]),
            SimpleNamespace(status="offline", last_check_at=datetime.utcnow(), tags=[]),
        ])

        self.assertEqual(stats, {"total": 1, "online": 0, "offline": 1, "unknown": 0})


if __name__ == "__main__":
    unittest.main()
