"""
Central configuration loader. Supports YAML config and environment variable overrides.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load config from YAML; merge with defaults. Path can be overridden by ARTICLEWRITER_CONFIG env."""
    import os

    base = Path(__file__).resolve().parent.parent.parent
    default_path = base / "config" / "default.yaml"
    path = config_path or os.environ.get("ARTICLEWRITER_CONFIG") or default_path
    path = Path(path)
    if not path.is_absolute():
        path = base / path
    return _load_yaml(path)


class EnvSettings(BaseSettings):
    """API keys and secrets from environment. Never commit .env to version control."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, description="OpenAI API key for synthesis/generation")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key (alternative LLM)")
    semantic_scholar_api_key: str | None = Field(default=None, description="Optional; higher rate limit")
    # CrossRef does not require a key for public use; polite pool: mailto in User-Agent


def get_env_settings() -> EnvSettings:
    return EnvSettings()
