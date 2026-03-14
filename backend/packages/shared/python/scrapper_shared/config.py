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
    search_provider: Literal["manual"] = Field(default="manual", alias="SEARCH_PROVIDER")
    allowed_domains: str = Field(default="", alias="ALLOWED_DOMAINS")

    user_agent: str = Field(
        default="RomaniaProductDiscoveryBot/1.0 (+contact: admin@example.com)",
        alias="USER_AGENT",
    )
    request_timeout_seconds: int = Field(default=12, alias="REQUEST_TIMEOUT_SECONDS")
    playwright_timeout_seconds: int = Field(default=15000, alias="PLAYWRIGHT_TIMEOUT_SECONDS")
    max_fetch_retries: int = Field(default=2, alias="MAX_FETCH_RETRIES")
    scraper_concurrency: int = Field(default=6, alias="SCRAPER_CONCURRENCY")
    scrape_batch_size: int = Field(default=25, alias="SCRAPE_BATCH_SIZE")
    manual_top_urls_per_domain: int = Field(default=3, alias="MANUAL_TOP_URLS_PER_DOMAIN")
    http_max_connections: int = Field(default=100, alias="HTTP_MAX_CONNECTIONS")
    http_max_keepalive_connections: int = Field(default=40, alias="HTTP_MAX_KEEPALIVE_CONNECTIONS")
    fetch_cache_ttl_seconds: int = Field(default=600, alias="FETCH_CACHE_TTL_SECONDS")
    cache_ttl_hours: int = Field(default=24, alias="CACHE_TTL_HOURS")
    job_rate_limit_per_minute: int = Field(default=10, alias="JOB_RATE_LIMIT_PER_MINUTE")

    @property
    def allowed_domains_set(self) -> set[str]:
        domains: set[str] = set()
        for item in self.allowed_domains.split(","):
            value = item.strip().lower()
            if not value:
                continue
            value = value.replace("https://", "").replace("http://", "")
            value = value.split("/")[0]
            if value.startswith("www."):
                value = value[4:]
            if value:
                domains.add(value)
        return domains


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
