import unittest

from fastapi import Response
from starlette.requests import Request

from app.api.auth import set_one_time_admin_cookie, should_secure_admin_cookie


def _request(scheme: str) -> Request:
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "method": "POST",
            "path": "/api/auth/admin/verify",
            "headers": [],
            "query_string": b"",
            "server": ("hpcdeploy.local", 10086),
            "client": ("127.0.0.1", 12345),
        }
    )


class AdminCookieSecurityTests(unittest.TestCase):
    def test_admin_cookie_allows_plain_http_deployment(self) -> None:
        self.assertFalse(should_secure_admin_cookie(_request("http")))

    def test_admin_cookie_remains_secure_for_https_deployment(self) -> None:
        self.assertTrue(should_secure_admin_cookie(_request("https")))

    def test_one_time_grant_uses_a_separate_httponly_cookie(self) -> None:
        response = Response()

        set_one_time_admin_cookie(response, token="one-time-token", request=_request("http"))

        cookie = response.headers["set-cookie"]
        self.assertIn("admin_once_token=one-time-token", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=30", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn(" Secure", cookie)


if __name__ == "__main__":
    unittest.main()
