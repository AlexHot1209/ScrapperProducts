from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.models import CachedUrl
from scrapper_shared.cache_utils import ttl_expiry
from scrapper_shared.normalization import normalize_text
from scrapper_shared.url_scoring import domain_from_url, is_probably_relevant, score_url

GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def _parse_allowed_domains(raw: str | None) -> set[str]:
    if not raw:
        return set()
    domains: set[str] = set()
    for item in raw.split(","):
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


def _build_query(query: str, allowed_domains: set[str]) -> str:
    if allowed_domains:
        return query
    return f"{query} site:.ro"


def _absolute_url(base_url: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    return urljoin(base_url, href)


def _same_domain(url: str, allowed_domains: set[str]) -> bool:
    return domain_from_url(url) in allowed_domains


def _fetch_html(base_url: str) -> str:
    settings = get_settings()
    timeout = min(settings.request_timeout_seconds, 6)
    response = requests.get(
        base_url,
        timeout=timeout,
        headers={"User-Agent": settings.user_agent},
    )
    response.raise_for_status()
    return response.text


def _extract_links(html: str, base_url: str, allowed_domains: set[str]) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    links: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        url = _absolute_url(base_url, anchor["href"])
        if not url:
            continue
        if not _same_domain(url, allowed_domains):
            continue
        text = anchor.get_text(" ", strip=True)
        links.append((url, text))
    return links


def _manual_search(query: str, max_urls: int, allowed_domains: set[str]) -> list[dict[str, Any]]:
    if not allowed_domains:
        raise RuntimeError("ALLOWED_DOMAINS is required for manual discovery")

    tokens = [t for t in normalize_text(query).split() if len(t) >= 3]
    top_per_domain = 3
    scored: list[tuple[str, float]] = []
    seen: set[str] = set()

    for domain in sorted(allowed_domains):
        base_url = f"https://{domain}"
        try:
            html = _fetch_html(base_url)
        except Exception:
            try:
                html = _fetch_html(f"http://{domain}")
                base_url = f"http://{domain}"
            except Exception:
                continue

        links = _extract_links(html, base_url, allowed_domains)
        if not links:
            links = [(base_url, "")]

        per_domain_scored: list[tuple[str, float]] = []
        for url, text in links[:120]:
            if url in seen:
                continue
            seen.add(url)
            score = score_url(url, text, "")
            if tokens and any(token in url.lower() or token in text.lower() for token in tokens):
                score += 2.0
            per_domain_scored.append((url, score))

        per_domain_scored.sort(key=lambda item: item[1], reverse=True)
        scored.extend(per_domain_scored[:top_per_domain])

    scored.sort(key=lambda item: item[1], reverse=True)
    top = scored[:max_urls]
    return [{"link": url, "title": "", "snippet": ""} for url, _score in top]


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
                "q": query,
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
            "q": query,
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
    allowed_domains = _parse_allowed_domains(settings.allowed_domains)
    query_text = _build_query(query, allowed_domains)
    if settings.search_provider == "manual":
        raw = _manual_search(query_text, max_urls, allowed_domains)
        mapped = [
            (
                item.get("link", ""),
                score_url(item.get("link", ""), item.get("title", ""), item.get("snippet", "")),
            )
            for item in raw
        ]
        provider = "manual"
    elif settings.search_provider == "google":
        raw = _google_search(query_text, max_urls)
        mapped = [
            (
                item.get("link", ""),
                score_url(item.get("link", ""), item.get("title", ""), item.get("snippet", "")),
            )
            for item in raw
        ]
        provider = "google"
    else:
        raw = _serpapi_search(query_text, max_urls)
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
        if allowed_domains and domain_from_url(url) not in allowed_domains:
            continue
        if provider == "manual" or is_probably_relevant(url):
            unique.append((url, score))

    unique.sort(key=lambda item: item[1], reverse=True)
    top = unique[:max_urls]
    _persist_cache(db, query_normalized, provider, top)
    return [url for url, _ in top]
