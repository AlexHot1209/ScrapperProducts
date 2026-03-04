from datetime import UTC, datetime, timedelta
from hashlib import sha1


def cache_key_for_url(query_normalized: str, url: str) -> str:
    return sha1(f"{query_normalized}|{url}".encode("utf-8")).hexdigest()


def ttl_expiry(hours: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=hours)
