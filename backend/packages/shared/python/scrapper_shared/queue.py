from datetime import UTC, datetime, timedelta
from hashlib import sha1

import redis
from rq import Queue

from scrapper_shared.config import get_settings


def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(name=settings.rq_queue_name, connection=get_redis(), default_timeout=900)


def cache_key_for_url(query_normalized: str, url: str) -> str:
    return sha1(f"{query_normalized}|{url}".encode("utf-8")).hexdigest()


def ttl_expiry(hours: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=hours)
