import os
from pathlib import Path
import subprocess
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _import_config(**environment: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(environment)
    return subprocess.run(
        [sys.executable, "-c", "from app.core.config import settings; print(settings.app_env)"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_rejects_short_jwt_secret() -> None:
    result = _import_config(
        APP_ENV="production",
        SECRET_KEY="short-secret",
        HPCDEPLOY_ADMIN_PASSWORD="valid-admin-password",
    )

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_production_allows_user_selected_admin_password() -> None:
    result = _import_config(
        APP_ENV="production",
        SECRET_KEY="a" * 64,
        HPCDEPLOY_ADMIN_PASSWORD="admin123",
    )

    assert result.returncode == 0, result.stderr


def test_production_accepts_generated_strength_values() -> None:
    result = _import_config(
        APP_ENV="production",
        SECRET_KEY="a" * 64,
        HPCDEPLOY_ADMIN_PASSWORD="admin123",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "production"
