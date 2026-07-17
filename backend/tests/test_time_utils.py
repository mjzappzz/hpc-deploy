import unittest
from datetime import datetime

from app.core.time_utils import format_beijing_time


class TimeUtilsTests(unittest.TestCase):
    def test_formats_naive_utc_database_time_as_beijing_time(self) -> None:
        self.assertEqual(
            format_beijing_time(datetime(2026, 7, 17, 6, 0, 0)),
            "2026-07-17 14:00:00",
        )


if __name__ == "__main__":
    unittest.main()
