from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from scrapper_shared.cache_utils import ttl_expiry
from scrapper_shared.config import get_settings
from scrapper_shared.models import CachedUrl
from scrapper_shared.normalization import normalize_text
from scrapper_shared.scraping.fetch import AsyncFetcher
from scrapper_shared.url_scoring import domain_from_url, is_probably_relevant, score_url


def _absolute_url(base_url: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    return urljoin(base_url, href)


def _same_domain(url: str, allowed_domains: set[str]) -> bool:
    return domain_from_url(url) in allowed_domains


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


async def _fetch_domain_candidates(
    fetcher: AsyncFetcher,
    domain: str,
    tokens: list[str],
    top_per_domain: int,
    allowed_domains: set[str],
) -> list[tuple[str, float]]:
    candidates: list[tuple[str, float]] = []
    seen: set[str] = set()

    for base_url in (f"https://{domain}", f"http://{domain}"):
        try:
            outcome = await fetcher.fetch_html(base_url)
            html = outcome.html
            links = _extract_links(html, base_url, allowed_domains)
            if not links:
                links = [(base_url, "")]

            for url, text in links[:120]:
                if url in seen:
                    continue
                seen.add(url)
                score = score_url(url, text, "")
                if tokens and any(token in url.lower() or token in text.lower() for token in tokens):
                    score += 2.0
                candidates.append((url, score))
            break
        except Exception:
            continue

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[:top_per_domain]


async def _manual_search_async(query: str, max_urls: int, allowed_domains: set[str]) -> list[dict[str, Any]]:
    if not allowed_domains:
        raise RuntimeError("ALLOWED_DOMAINS is required for manual discovery")

    settings = get_settings()
    tokens = [t for t in normalize_text(query).split() if len(t) >= 3]
    top_per_domain = max(1, settings.manual_top_urls_per_domain)

    fetcher = AsyncFetcher()
    try:
        domain_jobs = [
            _fetch_domain_candidates(fetcher, domain, tokens, top_per_domain, allowed_domains)
            for domain in sorted(allowed_domains)
        ]
        per_domain = await asyncio.gather(*domain_jobs, return_exceptions=True)
    finally:
        await fetcher.close()

    scored: list[tuple[str, float]] = []
    seen: set[str] = set()
    for result in per_domain:
        if isinstance(result, Exception):
            continue
        for url, score in result:
            if url in seen:
                continue
            seen.add(url)
            scored.append((url, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [{"link": url, "title": "", "snippet": ""} for url, _score in scored[:max_urls]]


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


def discover_urls(db: Session, query: str, query_normalized: str, max_urls: int) -> list[str]:
    cached = _cached_urls(db, query_normalized)
    if cached and len(cached) >= min(10, max_urls):
        return [url for url, _ in cached[:max_urls]]

    settings = get_settings()
    if settings.search_provider != "manual":
        raise RuntimeError("Only SEARCH_PROVIDER=manual is supported")

    allowed_domains = settings.allowed_domains_set
    raw = asyncio.run(_manual_search_async(query, max_urls, allowed_domains))
    mapped = [
        (
            item.get("link", ""),
            score_url(item.get("link", ""), item.get("title", ""), item.get("snippet", "")),
        )
        for item in raw
    ]

    unique: list[tuple[str, float]] = []
    seen: set[str] = set()
    for url, score in mapped:
        if not url or url in seen:
            continue
        seen.add(url)
        if allowed_domains and domain_from_url(url) not in allowed_domains:
            continue
        if is_probably_relevant(url):
            unique.append((url, score))

    unique.sort(key=lambda item: item[1], reverse=True)
    top = unique[:max_urls]
    _persist_cache(db, query_normalized, "manual", top)
    return [url for url, _ in top]
