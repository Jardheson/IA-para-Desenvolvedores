from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    openai_api_key: Optional[str] = Field(default=None, repr=False)
    openai_model: str = "gpt-4o-mini"

    # Low-code / n8n
    n8n_webhook_url: Optional[str] = None

    # Tool
    tool_use_mock: bool = True
    tool_kb_api_url: str = "https://api.publicapis.org/entries"

    # Observabilidade
    log_level: LogLevel = "INFO"
    storage_path: Path = Path("./storage")

    # Governança
    max_steps: int = 20
    adversarial_threshold: float = 0.50
    http_timeout_seconds: int = 5

    def ensure_storage(self) -> None:
        (self.storage_path / "executions").mkdir(parents=True, exist_ok=True)
        self.storage_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_storage()
    return s


settings = get_settings()
