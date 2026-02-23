from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scrapper_shared.scraping.types import ExtractedProduct
from scrapper_shared.site_adapters.base import SiteAdapter


class DedemanAdapter(SiteAdapter):
    domains = {"dedeman.ro"}

    def extract(self, html: str, source_url: str) -> ExtractedProduct | None:
        soup = BeautifulSoup(html, "lxml")
        name_node = soup.select_one("h1.product-name")
        price_node = soup.select_one(".product-price")
        if not name_node:
            return None

        from scrapper_shared.normalization import parse_price

        price, currency = parse_price(price_node.get_text(" ", strip=True) if price_node else None)
        return ExtractedProduct(
            product_name=name_node.get_text(" ", strip=True),
            price=price,
            currency=currency or "RON",
            size_text=None,
            location_text="Romania",
            canonical_url=source_url,
            extraction_method="adapter:dedeman",
        )


ADAPTERS: list[type[SiteAdapter]] = [DedemanAdapter]


def pick_adapter(url: str) -> SiteAdapter | None:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for adapter_class in ADAPTERS:
        if adapter_class.matches(domain):
            return adapter_class()
    return None
