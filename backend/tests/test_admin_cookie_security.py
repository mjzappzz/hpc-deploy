import unittest

from starlette.requests import Request

from app.api.auth import should_secure_admin_cookie


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


if __name__ == "__main__":
    unittest.main()
