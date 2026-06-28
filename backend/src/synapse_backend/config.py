"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from ``.env`` or the process environment.

    All Slack-related tokens are required for the app to start.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    slack_bot_token: str = Field(default="", description="Bot User OAuth token (xoxb-...) — required for bot service")
    slack_app_token: str = Field(
        default="", description="App-Level token for Socket Mode (xapp-...) — required for bot service"
    )
    slack_signing_secret: str = Field(default="", description="Signing secret — required for bot service")

    slack_bot_user_id: str = Field(default="", description="Bot user ID, populated after startup")

    slack_user_token: str = Field(default="", description="User OAuth token (xoxp-...) for Slack RTS search")

    slack_decisions_channel_id: str = Field(
        default="",
        description="Channel ID (e.g. C123ABC) where Decision Cards are posted",
    )

    github_token: str = Field(
        default="",
        description="GitHub personal access token for repository search",
    )

    api_port: int = Field(default=8000, description="Port for the FastAPI /internal/answer server")

    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, etc.)")


settings = Settings()
