"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from ``.env`` or the process environment.

    All Slack-related tokens are required for the app to start.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    slack_bot_token: str = Field(min_length=1, description="Bot User OAuth token (xoxb-...)")
    slack_app_token: str = Field(
        min_length=1, description="App-Level token for Socket Mode (xapp-...)"
    )
    slack_signing_secret: str = Field(min_length=1, description="Signing secret from Basic Information")

    slack_bot_user_id: str = Field(default="", description="Bot user ID, populated after startup")

    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, etc.)")


settings = Settings()
