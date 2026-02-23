from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.database import SessionLocal
from scrapper_shared.discovery import discover_urls
from scrapper_shared.enums import RadiusOption
from scrapper_shared.models import Job, ProductResult
from scrapper_shared.scraping.pipeline import process_url

logger = logging.getLogger(__name__)


def _to_payload(model: ProductResult) -> dict[str, object]:
    return {
        "product_name": model.product_name,
        "normalized_name": model.normalized_name,
        "domain": model.domain,
        "source_url": model.source_url,
        "canonical_url": model.canonical_url,
        "price": model.price,
        "currency": model.currency,
        "size_text": model.size_text,
        "location_city": model.location_city,
        "location_address": model.location_address,
        "location_lat": model.location_lat,
        "location_lon": model.location_lon,
        "distance_km": model.distance_km,
        "location_unknown": model.location_unknown,
        "extraction_method": model.extraction_method,
    }


def _process_single(
    job_id: UUID,
    query_normalized: str,
    url: str,
    radius_option: RadiusOption,
    include_unknown: bool,
) -> dict[str, object] | None:
    db = SessionLocal()
    try:
        processed = process_url(
            db=db,
            query_normalized=query_normalized,
            job_id=job_id,
            url=url,
            radius_option=radius_option,
            include_unknown=include_unknown,
        )
        if processed.accepted and processed.result:
            return _to_payload(processed.result)
        return None
    finally:
        db.close()


def _dedupe_key(payload: dict[str, object]) -> tuple[str, str, str]:
    name = str(payload.get("normalized_name", ""))
    domain = str(payload.get("domain", ""))
    price = str(payload.get("price") or "")
    return (name, domain, price)


def _url_key(payload: dict[str, object]) -> str:
    return str(payload.get("canonical_url") or payload.get("source_url") or "")


def process_job(job_id_raw: str) -> None:
    settings = get_settings()
    db: Session = SessionLocal()
    started = time.monotonic()

    try:
        job_id = UUID(job_id_raw)
        job = db.get(Job, job_id)
        if not job:
            logger.error("Job %s not found", job_id_raw)
            return

        job.status = "running"
        job.error_message = None
        db.commit()

        try:
            urls = discover_urls(db, job.query, job.query_normalized, job.max_urls)
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error_message = f"Discovery failed: {exc}"
            db.commit()
            return

        urls = urls[: job.max_urls]
        job.total_candidate_urls = len(urls)
        db.commit()

        radius = RadiusOption(job.radius_option)
        dedupe_seen: set[tuple[str, str, str]] = set()
        canonical_seen: set[str] = set()

        with ThreadPoolExecutor(max_workers=settings.scraper_concurrency) as pool:
            futures = {
                pool.submit(
                    _process_single,
                    job.id,
                    job.query_normalized,
                    url,
                    radius,
                    job.include_unknown_location,
                ): url
                for url in urls
            }

            for future in as_completed(futures):
                if time.monotonic() - started > job.time_budget_seconds:
                    job.error_message = "Time budget reached before processing all URLs."
                    break

                job.processed_urls += 1
                try:
                    payload = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed URL %s: %s", futures[future], exc)
                    job.error_count += 1
                    db.commit()
                    continue

                if payload:
                    key = _dedupe_key(payload)
                    canonical = _url_key(payload)
                    if key not in dedupe_seen and canonical not in canonical_seen:
                        dedupe_seen.add(key)
                        canonical_seen.add(canonical)
                        raw_price = payload.get("price")
                        parsed_price = None
                        if isinstance(raw_price, (Decimal, float, int)):
                            parsed_price = raw_price
                        elif raw_price is not None:
                            try:
                                parsed_price = Decimal(str(raw_price))
                            except Exception:  # noqa: BLE001
                                parsed_price = None

                        row = ProductResult(
                            job_id=job.id,
                            product_name=str(payload["product_name"]),
                            normalized_name=str(payload["normalized_name"]),
                            domain=str(payload["domain"]),
                            source_url=str(payload["source_url"]),
                            canonical_url=str(payload["canonical_url"]) if payload["canonical_url"] else None,
                            price=parsed_price,
                            currency=str(payload["currency"]) if payload.get("currency") else None,
                            size_text=str(payload["size_text"]) if payload.get("size_text") else None,
                            location_city=str(payload["location_city"])
                            if payload.get("location_city")
                            else None,
                            location_address=str(payload["location_address"])
                            if payload.get("location_address")
                            else None,
                            location_lat=float(payload["location_lat"])
                            if payload.get("location_lat") is not None
                            else None,
                            location_lon=float(payload["location_lon"])
                            if payload.get("location_lon") is not None
                            else None,
                            distance_km=float(payload["distance_km"])
                            if payload.get("distance_km") is not None
                            else None,
                            location_unknown=bool(payload.get("location_unknown", True)),
                            extraction_method=str(payload["extraction_method"]),
                        )
                        db.add(row)
                        job.found_products += 1

                db.commit()

        if job.status != "failed":
            job.status = "done"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Worker failed for job %s: %s", job_id_raw, exc)
        if "job" in locals() and job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()
