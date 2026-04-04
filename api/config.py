from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Disaster Damage Assessment API"
    app_env: str = "dev"
    app_version: str = "0.1.0"
    api_key: str = ""
    database_url: str = ""
    openai_api_key: str = ""
    predictions_metadata_path: str = "evaluation/predictions_with_metadata.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
