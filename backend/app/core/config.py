from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "hpc_control_panel.db"


class Settings(BaseSettings):
    app_name: str = "HPCDeploy"
    app_env: str = "development"
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    # ── JWT ──
    # 生产环境必须设置 SECRET_KEY，可以使用 openssl rand -hex 32 生成
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 480  # 8 小时
    hpcdeploy_temporary_admin_mode_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

if settings.app_env == "production":
    if (
        not settings.secret_key
        or settings.secret_key == "dev-secret-key-change-in-production"
        or len(settings.secret_key) < 32
    ):
        raise RuntimeError("production requires a non-default SECRET_KEY of at least 32 characters")
