import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.auth import AdminVerifyRequest, issue_temporary_admin_session, settings
from app.core.auth import create_admin_token, decode_admin_token, require_admin_token


class AdminSessionDurationTests(unittest.TestCase):
    def test_development_grant_is_short_lived_and_single_use(self) -> None:
        response = issue_temporary_admin_session(tab_id="tab-development")
        payload = decode_admin_token(response.token)

        self.assertEqual(response.expires_in, 30)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["tab_id"], "tab-development")
        self.assertEqual(payload["scope"], "admin_once")
        self.assertIn("exp", payload)
        self.assertEqual(
            require_admin_token(
                admin_token=None,
                x_admin_token=response.token,
                x_admin_tab_id="tab-development",
            ),
            response.token,
        )
        with self.assertRaises(HTTPException) as replayed:
            require_admin_token(
                admin_token=None,
                x_admin_token=response.token,
                x_admin_tab_id="tab-development",
            )
        self.assertEqual(replayed.exception.status_code, 403)

    def test_development_session_is_not_available_outside_development(self) -> None:
        with patch.object(settings, "app_env", "production"):
            with self.assertRaises(HTTPException) as denied:
                issue_temporary_admin_session(tab_id="tab-production")
        self.assertEqual(denied.exception.status_code, 404)

    def test_wrong_tab_does_not_consume_the_one_time_grant(self) -> None:
        response = issue_temporary_admin_session(tab_id="tab-owner")

        with self.assertRaises(HTTPException) as wrong_tab:
            require_admin_token(
                admin_token=None,
                x_admin_token=response.token,
                x_admin_tab_id="tab-other",
            )
        self.assertEqual(wrong_tab.exception.status_code, 403)
        self.assertEqual(
            require_admin_token(
                admin_token=None,
                x_admin_token=response.token,
                x_admin_tab_id="tab-owner",
            ),
            response.token,
        )

    def test_production_session_requires_the_explicit_temporary_mode_switch(self) -> None:
        with patch.object(settings, "app_env", "production"), patch.object(settings, "hpcdeploy_temporary_admin_mode_enabled", True):
            response = issue_temporary_admin_session(tab_id="tab-production-enabled")
        self.assertEqual(response.expires_in, 30)
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
            AdminVerifyRequest(password="test", duration_minutes=1, tab_id="tab-development")
        with self.assertRaises(ValidationError):
            AdminVerifyRequest(password="test", duration_minutes=120, tab_id="tab-invalid")


if __name__ == "__main__":
    unittest.main()
