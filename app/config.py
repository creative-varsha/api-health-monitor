from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "health_monitor"
    poll_interval_seconds: int = 300  # 5 minutes
    request_timeout_seconds: float = 10.0
    latency_threshold_ms: float = 2000.0  # slower than this counts as "degraded"
    log_level: str = "INFO"
    enable_poller: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
