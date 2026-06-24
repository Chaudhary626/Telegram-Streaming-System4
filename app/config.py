"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    STORAGE_CHANNEL_ID: str = ""

    # Database
    DB_HOST: str = "db"
    DB_PORT: int = 3306
    DB_USER: str = "streamapp"
    DB_PASSWORD: str = ""
    DB_NAME: str = "telegram_stream"

    # App
    BASE_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "change_me"
    ADMIN_SECRET_PATH: str = "admin-panel"
    STREAM_TOKEN_SECRET: str = "change_me_stream"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change_me"
    ENV: str = "development"

    @field_validator("STORAGE_CHANNEL_ID")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def storage_channels(self) -> List[int]:
        if not self.STORAGE_CHANNEL_ID:
            return []
        return [int(c) for c in self.STORAGE_CHANNEL_ID.split(",") if c.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
