"""Application settings loaded from environment variables.

Uses pydantic-settings to validate and load configuration once at import time.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Walk up from CWD looking for a ``.env`` file."""
    candidates = [Path.cwd()] + list(Path.cwd().parents)
    for d in candidates:
        env = d / ".env"
        if env.is_file():
            return str(env)
    return None


class Settings(BaseSettings):
    """Typed settings container for the Synapse AI/ML module.

    All values are loaded from environment variables (and optionally a .env file).
    """

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(min_length=1)
    brave_api_key: str = Field(min_length=1)

    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: int = 30
    openai_max_retries: int = 3

    brave_search_timeout_seconds: int = 15
    brave_search_max_retries: int = 2

    chroma_persist_directory: str = "./chroma_data"
    chroma_collection_name: str = "synapse_docs"


settings = Settings()
