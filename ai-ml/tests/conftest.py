"""Test session configuration: set required env vars before any imports."""

import os

os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("BRAVE_API_KEY", "bs-test-placeholder")
