import unittest
from unittest.mock import patch

from app.api import dashboard as dashboard_api
from app.core import project_storage
from app.db.database import SessionLocal


class DashboardSummaryLatencyTests(unittest.TestCase):
    def test_summary_does_not_scan_project_storage(self) -> None:
        with SessionLocal() as db:
            with patch.object(
                project_storage,
                "collect_project_storage",
                side_effect=AssertionError("dashboard summary must not scan project storage"),
            ):
                summary = dashboard_api.get_dashboard_summary(db)

        self.assertEqual(summary.storage.project_status, "unknown")
        self.assertIsNone(summary.storage.project_total_bytes)


if __name__ == "__main__":
    unittest.main()
