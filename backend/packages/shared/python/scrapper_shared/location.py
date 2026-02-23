import math
import re
from datetime import UTC, datetime

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.enums import BUCHAREST_COORDS
from scrapper_shared.models import GeocodeCache

CITY_HINTS = [
    "Bucuresti",
    "Cluj",
    "Timisoara",
    "Iasi",
    "Constanta",
    "Brasov",
    "Craiova",
    "Oradea",
    "Sibiu",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radius_km * c, 2)


def distance_from_bucharest_km(lat: float, lon: float) -> float:
    return haversine_km(BUCHAREST_COORDS[0], BUCHAREST_COORDS[1], lat, lon)


def extract_city_hint(text: str | None) -> str | None:
    if not text:
        return None
    for city in CITY_HINTS:
        if re.search(rf"\b{re.escape(city)}\b", text, re.IGNORECASE):
            return city
    return None


def geocode_location(db: Session, raw_location: str | None) -> dict[str, object] | None:
    if not raw_location:
        return None

    clean = " ".join(raw_location.split())[:500]
    if not clean:
        return None

    cached = db.execute(select(GeocodeCache).where(GeocodeCache.raw_location == clean)).scalar_one_or_none()
    if cached:
        return {
            "city": cached.city,
            "address": cached.address,
            "lat": cached.lat,
            "lon": cached.lon,
            "country": cached.country,
        }

    settings = get_settings()
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": clean, "format": "json", "limit": 1, "countrycodes": "ro"},
            headers={"User-Agent": settings.user_agent},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    if not data:
        return None

    best = data[0]
    lat = float(best.get("lat"))
    lon = float(best.get("lon"))
    display_name = best.get("display_name")
    city = extract_city_hint(display_name)

    cache = GeocodeCache(
        raw_location=clean,
        city=city,
        address=display_name,
        lat=lat,
        lon=lon,
        country="Romania",
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(cache)
    db.commit()

    return {"city": city, "address": display_name, "lat": lat, "lon": lon, "country": "Romania"}
