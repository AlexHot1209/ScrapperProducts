from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.models import CachedUrl
from scrapper_shared.queue import ttl_expiry
from scrapper_shared.url_scoring import is_probably_relevant, score_url

GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def _cached_urls(db: Session, query_normalized: str) -> list[tuple[str, float]]:
    now = datetime.now(UTC).replace(tzinfo=None)
    db.execute(delete(CachedUrl).where(CachedUrl.expires_at < now))
    db.commit()

    rows = db.execute(
        select(CachedUrl)
        .where(and_(CachedUrl.query_normalized == query_normalized, CachedUrl.expires_at >= now))
        .order_by(CachedUrl.score.desc())
    ).scalars()
    return [(row.url, row.score) for row in rows]


def _persist_cache(db: Session, query_normalized: str, provider: str, urls: list[tuple[str, float]]) -> None:
    ttl = ttl_expiry(get_settings().cache_ttl_hours)
    for url, score in urls:
        db.add(
            CachedUrl(
                query_normalized=query_normalized,
                provider=provider,
                url=url,
                score=score,
                expires_at=ttl,
            )
        )
    db.commit()


def _google_search(query: str, max_urls: int) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.google_cse_api_key or not settings.google_cse_cx:
        raise RuntimeError("Google CSE credentials are missing")

    session = requests.Session()
    items: list[dict[str, Any]] = []
    start = 1
    while len(items) < max_urls and start <= 91:
        response = session.get(
            GOOGLE_ENDPOINT,
            params={
                "q": f"{query} site:.ro",
                "key": settings.google_cse_api_key,
                "cx": settings.google_cse_cx,
                "num": min(10, max_urls - len(items)),
                "start": start,
                "hl": "ro",
                "lr": "lang_ro",
                "gl": "ro",
                "safe": "off",
            },
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
        )
        response.raise_for_status()
        payload = response.json()
        page_items = payload.get("items", [])
        if not page_items:
            break
        items.extend(page_items)
        start += 10
    return items


def _serpapi_search(query: str, max_urls: int) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.serpapi_api_key:
        raise RuntimeError("SerpAPI key is missing")

    response = requests.get(
        SERPAPI_ENDPOINT,
        params={
            "engine": "google",
            "q": f"{query} site:.ro",
            "api_key": settings.serpapi_api_key,
            "google_domain": "google.ro",
            "hl": "ro",
            "gl": "ro",
            "num": min(max_urls, 100),
        },
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("organic_results", [])


def discover_urls(db: Session, query: str, query_normalized: str, max_urls: int) -> list[str]:
    cached = _cached_urls(db, query_normalized)
    if cached and len(cached) >= min(10, max_urls):
        return [url for url, _ in cached[:max_urls]]

    settings = get_settings()
    if settings.search_provider == "google":
        raw = _google_search(query, max_urls)
        mapped = [
            (
                item.get("link", ""),
                score_url(item.get("link", ""), item.get("title", ""), item.get("snippet", "")),
            )
            for item in raw
        ]
        provider = "google"
    else:
        raw = _serpapi_search(query, max_urls)
        mapped = [
            (
                item.get("link", ""),
                score_url(item.get("link", ""), item.get("title", ""), item.get("snippet", "")),
            )
            for item in raw
        ]
        provider = "serpapi"

    unique: list[tuple[str, float]] = []
    seen: set[str] = set()
    for url, score in mapped:
        if not url or url in seen:
            continue
        seen.add(url)
        if is_probably_relevant(url):
            unique.append((url, score))

    unique.sort(key=lambda item: item[1], reverse=True)
    top = unique[:max_urls]
    _persist_cache(db, query_normalized, provider, top)
    return [url for url, _ in top]
