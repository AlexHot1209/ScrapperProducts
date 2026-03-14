from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from scrapper_shared.config import get_settings


class FetchError(Exception):
    pass


@dataclass(slots=True)
class FetchOutcome:
    html: str
    method: str


class AsyncFetcher:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.scraper_concurrency)
        self._domain_last_access: dict[str, float] = defaultdict(float)
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._robots_cache: dict[str, tuple[float, RobotFileParser]] = {}
        self._html_cache: dict[str, tuple[float, FetchOutcome]] = {}
        self._html_cache_lock = asyncio.Lock()

        limits = httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
            keepalive_expiry=30.0,
        )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=float(settings.request_timeout_seconds), write=10.0, pool=10.0),
            headers={"User-Agent": settings.user_agent, "Accept-Language": "ro,en;q=0.8"},
            follow_redirects=True,
            limits=limits,
            http2=True,
        )
        self._playwright = None
        self._browser = None
        self._browser_context = None
        self._playwright_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()
        if self._browser_context:
            await self._browser_context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    async def _load_robots_parser(self, url: str) -> RobotFileParser:
        domain = self._domain(url)
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            response = await self._client.get(robots_url)
            if response.is_success:
                parser.parse(response.text.splitlines())
            else:
                parser.parse(["User-agent: *", "Allow: /"])
        except Exception:
            parser.parse(["User-agent: *", "Allow: /"])
        return parser

    async def _can_fetch(self, url: str) -> bool:
        domain = self._domain(url)
        now = time.time()

        cached = self._robots_cache.get(domain)
        if not cached or now - cached[0] > 3600:
            parser = await self._load_robots_parser(url)
            self._robots_cache[domain] = (now, parser)
            cached = (now, parser)

        return cached[1].can_fetch(self._settings.user_agent, url)

    async def _throttle(self, url: str) -> None:
        domain = self._domain(url)
        lock = self._domain_locks[domain]
        async with lock:
            now = time.time()
            elapsed = now - self._domain_last_access[domain]
            minimum_interval = 0.25 + random.uniform(0.05, 0.2)
            if elapsed < minimum_interval:
                await asyncio.sleep(minimum_interval - elapsed)
            self._domain_last_access[domain] = time.time()

    async def _http_fetch(self, url: str) -> FetchOutcome:
        if not await self._can_fetch(url):
            raise FetchError("Blocked by robots.txt")

        max_attempts = max(1, self._settings.max_fetch_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                await self._throttle(url)
                response = await self._client.get(url)
                if response.status_code in (429, 503):
                    raise FetchError(f"Temporary blocked with {response.status_code}")
                response.raise_for_status()
                html = response.text
                if "enable javascript" in html.lower() or len(html) < 400:
                    raise FetchError("Likely JS-heavy page")
                return FetchOutcome(html=html, method="httpx")
            except (httpx.HTTPError, FetchError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(min(1.0, 0.25 * attempt))

        raise FetchError(str(last_error) if last_error else "Request fetch failed")

    async def _ensure_browser(self) -> None:
        if self._browser_context:
            return

        async with self._playwright_lock:
            if self._browser_context:
                return
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._browser_context = await self._browser.new_context(
                user_agent=self._settings.user_agent,
                locale="ro-RO",
            )

    async def _playwright_fetch(self, url: str) -> FetchOutcome:
        if not await self._can_fetch(url):
            raise FetchError("Blocked by robots.txt")

        await self._ensure_browser()
        await self._throttle(url)

        assert self._browser_context is not None
        page = await self._browser_context.new_page()
        try:
            await page.goto(
                url,
                timeout=self._settings.playwright_timeout_seconds,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(1200)
            html = await page.content()
            return FetchOutcome(html=html, method="playwright-reused")
        finally:
            await page.close()

    async def fetch_html(self, url: str) -> FetchOutcome:
        async with self._html_cache_lock:
            cached = self._html_cache.get(url)
            if cached and (time.time() - cached[0]) <= self._settings.fetch_cache_ttl_seconds:
                return cached[1]

        async with self._semaphore:
            try:
                outcome = await self._http_fetch(url)
            except FetchError as exc:
                if "js-heavy" not in str(exc).lower():
                    raise
                outcome = await self._playwright_fetch(url)

        async with self._html_cache_lock:
            self._html_cache[url] = (time.time(), outcome)
        return outcome

    async def fetch_many(self, urls: list[str]) -> dict[str, FetchOutcome | Exception]:
        async def _runner(url: str) -> tuple[str, FetchOutcome | Exception]:
            try:
                return url, await self.fetch_html(url)
            except Exception as exc:  # noqa: BLE001
                return url, exc

        results = await asyncio.gather(*[_runner(url) for url in urls])
        return {url: value for url, value in results}
