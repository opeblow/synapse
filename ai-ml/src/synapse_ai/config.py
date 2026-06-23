"""Application settings loaded from environment variables.

Uses pydantic-settings to validate and load configuration once at import time.
Reads from ``os.environ`` only — no file discovery (callers should call
``dotenv.load_dotenv()`` before importing this module if they want file-based
overrides).
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Typed settings container for the Synapse AI/ML module.

    All values are loaded from environment variables (and optionally a .env file).
    The ``.env`` file must be loaded into ``os.environ`` by the caller (e.g. via
    ``dotenv.load_dotenv()``) before the module-level ``settings`` singleton is
    first accessed.
    """

    model_config = SettingsConfigDict(
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

    chroma_persist_directory: str = str(_PROJECT_ROOT / "chroma_data")
    chroma_collection_name: str = "synapse_docs"

    github_token: str = Field(default="", description="GitHub personal access token")
    github_repo: str = Field(default="", description="GitHub repo (owner/name) for code search")


settings = Settings()
