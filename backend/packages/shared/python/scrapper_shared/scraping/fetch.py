from __future__ import annotations

import random
import time
from collections import defaultdict
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from scrapper_shared.config import get_settings


class FetchError(Exception):
    pass


_robots_cache: dict[str, tuple[float, RobotFileParser]] = {}
_domain_last_access: dict[str, float] = defaultdict(float)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _can_fetch(url: str, user_agent: str) -> bool:
    domain = _domain(url)
    robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
    now = time.time()

    cached = _robots_cache.get(domain)
    if not cached or now - cached[0] > 3600:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            return True
        _robots_cache[domain] = (now, parser)
        cached = (now, parser)

    return cached[1].can_fetch(user_agent, url)


def _throttle(url: str) -> None:
    domain = _domain(url)
    now = time.time()
    elapsed = now - _domain_last_access[domain]
    minimum_interval = 0.8 + random.uniform(0.1, 0.6)
    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)
    _domain_last_access[domain] = time.time()


@retry(
    retry=retry_if_exception_type((requests.RequestException, FetchError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=6),
    reraise=True,
)
def _requests_fetch(url: str) -> tuple[str, str]:
    settings = get_settings()
    if not _can_fetch(url, settings.user_agent):
        raise FetchError("Blocked by robots.txt")

    _throttle(url)
    response = requests.get(
        url,
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": settings.user_agent, "Accept-Language": "ro,en;q=0.8"},
    )

    if response.status_code in (429, 503):
        raise FetchError(f"Temporary blocked with {response.status_code}")

    response.raise_for_status()
    html = response.text
    if "enable javascript" in html.lower() or len(html) < 400:
        raise FetchError("Likely JS-heavy page")
    return html, "requests"


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
    except (FetchError, RetryError, requests.RequestException):
        return _playwright_fetch(url)
