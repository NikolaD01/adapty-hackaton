"""Settings: the only place where configuration and secrets live (CLAUDE.md §4)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    adapty_app_id: str = "c6c7bdd1-1010-4343-8b29-837a77793cab"
    adapty_secret_key: SecretStr = SecretStr("")
    adapty_cli: str = "adapty"
    adapty_api_base: str = "https://api.adapty.io"
    offline_data_dir: str = "./data/offline"
    llm_provider: str = "openai"
    llm_model: str = "gpt-6-luna"
    openai_api_key: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
