import unittest

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.auth import AdminVerifyRequest
from app.core.auth import create_admin_token, decode_admin_token, require_admin_token


class AdminSessionDurationTests(unittest.TestCase):
    def test_unlimited_session_has_no_expiry_and_requires_its_tab_id(self) -> None:
        token = create_admin_token(duration_minutes=None, tab_id="tab-current")
        payload = decode_admin_token(token)

        self.assertIsNotNone(payload)
        self.assertNotIn("exp", payload)
        self.assertEqual(payload["tab_id"], "tab-current")
        self.assertEqual(
            require_admin_token(admin_token=token, x_admin_token=None, x_admin_tab_id="tab-current"),
            token,
        )
        with self.assertRaises(HTTPException) as missing_tab:
            require_admin_token(admin_token=token, x_admin_token=None, x_admin_tab_id=None)
        self.assertEqual(missing_tab.exception.status_code, 403)

    def test_timed_session_keeps_expiry_and_requires_its_tab_id(self) -> None:
        token = create_admin_token(duration_minutes=15, tab_id="tab-timed")
        payload = decode_admin_token(token)

        self.assertIsNotNone(payload)
        self.assertIn("exp", payload)
        self.assertEqual(payload["tab_id"], "tab-timed")
        with self.assertRaises(HTTPException) as wrong_tab:
            require_admin_token(admin_token=token, x_admin_token=None, x_admin_tab_id="another-tab")
        self.assertEqual(wrong_tab.exception.status_code, 403)

    def test_verify_request_only_accepts_allowlisted_durations(self) -> None:
        self.assertEqual(
            AdminVerifyRequest(password="test", duration_minutes=30, tab_id="tab-30").duration_minutes,
            30,
        )
        self.assertIsNone(AdminVerifyRequest(password="test", duration_minutes=None, tab_id="tab-open").duration_minutes)
        with self.assertRaises(ValidationError):
            AdminVerifyRequest(password="test", duration_minutes=120, tab_id="tab-invalid")


if __name__ == "__main__":
    unittest.main()
