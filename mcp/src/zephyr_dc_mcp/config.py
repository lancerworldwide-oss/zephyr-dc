"""Environment-driven configuration for zephyr-dc-mcp."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from host/container environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model: str = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")
    openai_org: str | None = Field(default=None, validation_alias="OPENAI_ORG")
    openai_api_type: str | None = Field(default=None, validation_alias="OPENAI_API_TYPE")

    mcp_host: str = Field(default="0.0.0.0", validation_alias="ZEPHYR_DC_MCP_HOST")
    mcp_port: int = Field(default=8765, validation_alias="ZEPHYR_DC_MCP_PORT")
    api_token: str | None = Field(default=None, validation_alias="ZEPHYR_DC_API_TOKEN")

    zephyr_base: str | None = Field(default=None, validation_alias="ZEPHYR_BASE")
    renode_path: str = Field(default="/opt/renode", validation_alias="ZEPHYR_DC_RENODE_PATH")

    max_read_bytes: int = Field(default=1_048_576, validation_alias="ZEPHYR_DC_MAX_READ_BYTES")
    max_output_chars: int = Field(default=200_000, validation_alias="ZEPHYR_DC_MAX_OUTPUT_CHARS")
    agent_max_iterations: int = Field(default=20, validation_alias="ZEPHYR_DC_AGENT_MAX_ITERATIONS")
    default_job_timeout_sec: int = Field(
        default=3600,
        validation_alias="ZEPHYR_DC_JOB_TIMEOUT_SEC",
    )

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
