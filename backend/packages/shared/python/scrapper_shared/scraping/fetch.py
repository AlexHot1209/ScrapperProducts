from __future__ import annotations

import random
import time
from collections import defaultdict
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from scrapper_shared.config import get_settings


class FetchError(Exception):
    pass


# domain -> (fetched_at_epoch, robots_parser)
_robots_cache: dict[str, tuple[float, RobotFileParser]] = {}
_domain_last_access: dict[str, float] = defaultdict(float)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _load_robots_parser(url: str, user_agent: str) -> RobotFileParser:
    settings = get_settings()
    domain = _domain(url)
    robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)

    # Avoid RobotFileParser.read() because it performs an unbounded urllib request.
    try:
        response = requests.get(
            robots_url,
            timeout=min(3, settings.request_timeout_seconds),
            headers={"User-Agent": user_agent, "Accept-Language": "ro,en;q=0.8"},
        )
        if response.ok:
            parser.parse(response.text.splitlines())
        else:
            # If robots cannot be loaded, fail-open to avoid blocking scraping entirely.
            parser.parse(["User-agent: *", "Allow: /"])
    except Exception:
        parser.parse(["User-agent: *", "Allow: /"])
    return parser


def _can_fetch(url: str, user_agent: str) -> bool:
    domain = _domain(url)
    now = time.time()

    cached = _robots_cache.get(domain)
    if not cached or now - cached[0] > 3600:
        parser = _load_robots_parser(url, user_agent)
        _robots_cache[domain] = (now, parser)
        cached = (now, parser)

    return cached[1].can_fetch(user_agent, url)


def _throttle(url: str) -> None:
    domain = _domain(url)
    now = time.time()
    elapsed = now - _domain_last_access[domain]
    minimum_interval = 0.25 + random.uniform(0.05, 0.20)
    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)
    _domain_last_access[domain] = time.time()


def _requests_fetch(url: str) -> tuple[str, str]:
    settings = get_settings()
    if not _can_fetch(url, settings.user_agent):
        raise FetchError("Blocked by robots.txt")

    max_attempts = max(1, settings.max_fetch_retries + 1)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            _throttle(url)
            response = requests.get(
                url,
                timeout=(3, settings.request_timeout_seconds),
                headers={"User-Agent": settings.user_agent, "Accept-Language": "ro,en;q=0.8"},
            )

            if response.status_code in (429, 503):
                raise FetchError(f"Temporary blocked with {response.status_code}")

            response.raise_for_status()
            html = response.text
            if "enable javascript" in html.lower() or len(html) < 400:
                raise FetchError("Likely JS-heavy page")
            return html, "requests"
        except (requests.RequestException, FetchError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            sleep_s = min(1.0, 0.25 * attempt)
            time.sleep(sleep_s)

    raise FetchError(str(last_error) if last_error else "Request fetch failed")


def _playwright_fetch(url: str) -> tuple[str, str]:
    settings = get_settings()
    from playwright.sync_api import sync_playwright

    if not _can_fetch(url, settings.user_agent):
        raise FetchError("Blocked by robots.txt")

    _throttle(url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=settings.user_agent, locale="ro-RO")
        page = context.new_page()
        page.goto(url, timeout=settings.playwright_timeout_seconds, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        html = page.content()
        context.close()
        browser.close()
    return html, "playwright"


def fetch_html(url: str) -> tuple[str, str]:
    try:
        return _requests_fetch(url)
    except FetchError as exc:
        # Playwright fallback is very expensive. Use it only for likely JS-heavy pages.
        if "js-heavy" not in str(exc).lower():
            raise
        return _playwright_fetch(url)
