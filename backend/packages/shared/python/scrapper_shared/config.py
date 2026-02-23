from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Romanian Product Discovery API"
    environment: Literal["dev", "prod", "test"] = "dev"

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/product_scraper",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    rq_queue_name: str = Field(default="product-scraper", alias="RQ_QUEUE_NAME")

    search_provider: Literal["google", "serpapi"] = Field(default="google", alias="SEARCH_PROVIDER")
    google_cse_api_key: str | None = Field(default=None, alias="GOOGLE_CSE_API_KEY")
    google_cse_cx: str | None = Field(default=None, alias="GOOGLE_CSE_CX")
    serpapi_api_key: str | None = Field(default=None, alias="SERPAPI_API_KEY")

    user_agent: str = Field(
        default="RomaniaProductDiscoveryBot/1.0 (+contact: admin@example.com)",
        alias="USER_AGENT",
    )
    request_timeout_seconds: int = Field(default=12, alias="REQUEST_TIMEOUT_SECONDS")
    playwright_timeout_seconds: int = Field(default=15000, alias="PLAYWRIGHT_TIMEOUT_SECONDS")
    max_fetch_retries: int = Field(default=2, alias="MAX_FETCH_RETRIES")
    scraper_concurrency: int = Field(default=6, alias="SCRAPER_CONCURRENCY")
    cache_ttl_hours: int = Field(default=24, alias="CACHE_TTL_HOURS")
    job_rate_limit_per_minute: int = Field(default=10, alias="JOB_RATE_LIMIT_PER_MINUTE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
