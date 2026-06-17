from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HPCDeploy"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/hpc_control_panel.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

