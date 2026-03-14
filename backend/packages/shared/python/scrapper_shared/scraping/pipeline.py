from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from scrapper_shared.cache_utils import cache_key_for_url, ttl_expiry
from scrapper_shared.config import get_settings
from scrapper_shared.enums import RADIUS_KM, RadiusOption
from scrapper_shared.location import distance_from_bucharest_km, extract_city_hint, geocode_location
from scrapper_shared.models import CachedResult, ProductResult
from scrapper_shared.normalization import normalize_product_name
from scrapper_shared.scraping.adapters import pick_adapter
from scrapper_shared.scraping.extract import extract_product
from scrapper_shared.url_scoring import domain_from_url


@dataclass(slots=True)
class ProcessedItem:
    accepted: bool
    result: ProductResult | None
    from_cache: bool


def include_by_radius(
    radius_option: RadiusOption,
    include_unknown: bool,
    distance_km: float | None,
    city: str | None,
) -> bool:
    if radius_option == RadiusOption.all_ro:
        return True

    if radius_option == RadiusOption.bucharest and city:
        city_normalized = (
            city.lower().replace("ă", "a").replace("â", "a").replace("ș", "s").replace("ț", "t")
        )
        if "bucure" in city_normalized:
            return True

    if distance_km is None:
        return include_unknown

    max_radius = RADIUS_KM[radius_option]
    return distance_km <= max_radius


def _load_cached(db: Session, query_normalized: str, url: str) -> CachedResult | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    key = cache_key_for_url(query_normalized, url)
    return db.execute(
        select(CachedResult).where(and_(CachedResult.cache_key == key, CachedResult.expires_at >= now))
    ).scalar_one_or_none()


def _save_cache(db: Session, query_normalized: str, result: ProductResult) -> None:
    key = cache_key_for_url(query_normalized, result.source_url)
    existing = db.execute(select(CachedResult).where(CachedResult.cache_key == key)).scalar_one_or_none()
    ttl = ttl_expiry(get_settings().cache_ttl_hours)
    if existing:
        existing.product_name = result.product_name
        existing.price = result.price
        existing.currency = result.currency
        existing.size_text = result.size_text
        existing.location_city = result.location_city
        existing.location_address = result.location_address
        existing.location_lat = result.location_lat
        existing.location_lon = result.location_lon
        existing.expires_at = ttl
    else:
        db.add(
            CachedResult(
                cache_key=key,
                query_normalized=query_normalized,
                domain=result.domain,
                source_url=result.source_url,
                product_name=result.product_name,
                price=result.price,
                currency=result.currency,
                size_text=result.size_text,
                location_city=result.location_city,
                location_address=result.location_address,
                location_lat=result.location_lat,
                location_lon=result.location_lon,
                expires_at=ttl,
            )
        )


def process_cached_url(
    db: Session,
    query_normalized: str,
    job_id,
    url: str,
    radius_option: RadiusOption,
    include_unknown: bool,
) -> ProcessedItem:
    cached = _load_cached(db, query_normalized, url)
    if not cached:
        return ProcessedItem(accepted=False, result=None, from_cache=False)

    distance = (
        distance_from_bucharest_km(cached.location_lat, cached.location_lon)
        if cached.location_lat is not None and cached.location_lon is not None
        else None
    )
    if not include_by_radius(radius_option, include_unknown, distance, cached.location_city):
        return ProcessedItem(accepted=False, result=None, from_cache=True)

    model = ProductResult(
        job_id=job_id,
        product_name=cached.product_name,
        normalized_name=normalize_product_name(cached.product_name),
        domain=cached.domain,
        source_url=cached.source_url,
        canonical_url=cached.source_url,
        price=cached.price,
        currency=cached.currency,
        size_text=cached.size_text,
        location_city=cached.location_city,
        location_address=cached.location_address,
        location_lat=cached.location_lat,
        location_lon=cached.location_lon,
        distance_km=distance,
        location_unknown=cached.location_lat is None,
        extraction_method="cache",
    )
    return ProcessedItem(accepted=True, result=model, from_cache=True)


def process_url_with_html(
    db: Session,
    query_normalized: str,
    job_id,
    url: str,
    html: str,
    extraction_method: str,
    radius_option: RadiusOption,
    include_unknown: bool,
) -> ProcessedItem:
    adapter = pick_adapter(url)
    extracted = adapter.extract(html, url) if adapter else extract_product(html, url)
    if not extracted or not extracted.product_name:
        return ProcessedItem(accepted=False, result=None, from_cache=False)

    location_data = geocode_location(db, extracted.location_text)
    city = extract_city_hint(extracted.location_text) or (
        str(location_data.get("city")) if location_data and location_data.get("city") else None
    )
    lat = float(location_data["lat"]) if location_data and location_data.get("lat") is not None else None
    lon = float(location_data["lon"]) if location_data and location_data.get("lon") is not None else None
    distance = distance_from_bucharest_km(lat, lon) if lat is not None and lon is not None else None

    if not include_by_radius(radius_option, include_unknown, distance, city):
        return ProcessedItem(accepted=False, result=None, from_cache=False)

    model = ProductResult(
        job_id=job_id,
        product_name=extracted.product_name,
        normalized_name=normalize_product_name(extracted.product_name),
        domain=domain_from_url(url),
        source_url=url,
        canonical_url=extracted.canonical_url,
        price=extracted.price,
        currency=extracted.currency,
        size_text=extracted.size_text,
        location_city=city,
        location_address=str(location_data.get("address")) if location_data else None,
        location_lat=lat,
        location_lon=lon,
        distance_km=distance,
        location_unknown=lat is None,
        extraction_method=extraction_method,
    )
    _save_cache(db, query_normalized, model)
    return ProcessedItem(accepted=True, result=model, from_cache=False)
