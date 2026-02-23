from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapper_shared.normalization import extract_size, parse_price
from scrapper_shared.scraping.types import ExtractedProduct

LEI_REGEX = re.compile(
    r"(\d{1,3}(?:[\.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[\.,]\d{1,2})?)\s*(?:lei|ron)",
    re.IGNORECASE,
)
LOCATION_REGEX = re.compile(
    r"(Bucuresti|București|Cluj|Timisoara|Timișoara|Iasi|Iași|Constanta|Constanța|Brasov|Brașov)",
    re.IGNORECASE,
)


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _extract_jsonld_product(soup: BeautifulSoup) -> ExtractedProduct | None:
    blocks = soup.find_all("script", attrs={"type": "application/ld+json"})
    for block in blocks:
        raw = block.string or block.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        candidates: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            candidates = [payload]
        elif isinstance(payload, list):
            candidates = [item for item in payload if isinstance(item, dict)]

        for candidate in candidates:
            content_type = str(candidate.get("@type", "")).lower()
            if "product" not in content_type:
                continue

            name = candidate.get("name")
            offers = candidate.get("offers")
            price: Decimal | None = None
            currency: str | None = None
            if isinstance(offers, dict):
                if offers.get("price") is not None:
                    price, currency = parse_price(f"{offers.get('price')} {offers.get('priceCurrency', '')}")
                currency = offers.get("priceCurrency") or currency

            size = _first_non_empty(
                candidate.get("size"),
                candidate.get("description"),
                candidate.get("sku"),
            )
            canonical = candidate.get("url")
            brand = candidate.get("brand")
            location = brand.get("name") if isinstance(brand, dict) else None

            return ExtractedProduct(
                product_name=name or "Unknown product",
                price=price,
                currency=currency or "RON",
                size_text=extract_size(size) or size,
                location_text=location,
                canonical_url=canonical,
                extraction_method="jsonld",
            )
    return None


def _extract_microdata(soup: BeautifulSoup) -> ExtractedProduct | None:
    node = soup.select_one('[itemtype*="Product"]')
    if not node:
        return None

    name_node = node.select_one('[itemprop="name"]')
    price_node = node.select_one('[itemprop="price"]')
    currency_node = node.select_one('[itemprop="priceCurrency"]')
    size_node = node.select_one('[itemprop="size"]')

    name = _first_non_empty(
        name_node.get_text(strip=True) if name_node else None,
        soup.h1.get_text(strip=True) if soup.h1 else None,
        soup.title.get_text(strip=True) if soup.title else None,
    )
    price_raw = _first_non_empty(
        price_node.get("content") if price_node else None,
        price_node.get_text(strip=True) if price_node else None,
    )
    price, currency = parse_price(price_raw)
    currency = _first_non_empty(currency_node.get("content") if currency_node else None, currency, "RON")
    size_raw = _first_non_empty(size_node.get_text(strip=True) if size_node else None, node.get_text(" ", strip=True))

    return ExtractedProduct(
        product_name=name or "Unknown product",
        price=price,
        currency=currency,
        size_text=extract_size(size_raw) or size_raw,
        location_text=None,
        canonical_url=None,
        extraction_method="microdata",
    )


def _extract_opengraph(soup: BeautifulSoup) -> ExtractedProduct | None:
    title = soup.find("meta", property="og:title")
    if not title:
        return None

    name = title.get("content")
    description = soup.find("meta", property="og:description")
    description_text = description.get("content") if description else None
    price, currency = parse_price(description_text)
    canonical = soup.find("link", rel="canonical")
    canonical_url = canonical.get("href") if canonical else None

    return ExtractedProduct(
        product_name=name or "Unknown product",
        price=price,
        currency=currency or "RON",
        size_text=extract_size(description_text),
        location_text=description_text,
        canonical_url=canonical_url,
        extraction_method="opengraph",
    )


def _extract_heuristic(soup: BeautifulSoup, source_url: str) -> ExtractedProduct | None:
    h1 = soup.h1.get_text(" ", strip=True) if soup.h1 else None
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    text_blob = soup.get_text(" ", strip=True)[:5000]

    name = _first_non_empty(h1, title)
    if not name:
        return None

    price_match = LEI_REGEX.search(text_blob)
    price, currency = parse_price(price_match.group(0) if price_match else None)
    location_match = LOCATION_REGEX.search(text_blob)
    size = extract_size(text_blob)
    canonical = soup.find("link", rel="canonical")
    canonical_url = canonical.get("href") if canonical else source_url

    return ExtractedProduct(
        product_name=name,
        price=price,
        currency=currency or "RON",
        size_text=size,
        location_text=location_match.group(0) if location_match else None,
        canonical_url=urljoin(source_url, canonical_url) if canonical_url else source_url,
        extraction_method="heuristic",
    )


def extract_product(html: str, source_url: str) -> ExtractedProduct | None:
    soup = BeautifulSoup(html, "lxml")
    for extractor in (_extract_jsonld_product, _extract_microdata, _extract_opengraph):
        result = extractor(soup)
        if result and result.product_name:
            return result
    return _extract_heuristic(soup, source_url)
