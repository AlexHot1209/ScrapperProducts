from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Thread
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, asc, desc, func, select, text
from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.database import SessionLocal, get_db
from scrapper_shared.discovery import discover_urls
from scrapper_shared.enums import RadiusOption
from scrapper_shared.models import Job, ProductResult
from scrapper_shared.normalization import normalize_text
from scrapper_shared.scraping.pipeline import process_url
from scrapper_shared.rate_limit import InMemoryRateLimiter
from scrapper_shared.schemas import (
    CreateJobRequest,
    HealthResponse,
    JobStatusResponse,
    ResultItem,
    ResultsResponse,
)

router = APIRouter()
settings = get_settings()
rate_limiter = InMemoryRateLimiter(settings.job_rate_limit_per_minute)
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


def process_job_inline(job_id: UUID) -> None:
    db: Session = SessionLocal()
    started = time.monotonic()

    try:
        job = db.get(Job, job_id)
        if not job:
            logger.error("Job %s not found", job_id)
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
        logger.exception("Inline job failed for job %s: %s", job_id, exc)
        if "job" in locals() and job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()


def _job_to_response(job: Job) -> JobStatusResponse:
    progress = 0.0
    if job.total_candidate_urls > 0:
        progress = min(100.0, (job.processed_urls / job.total_candidate_urls) * 100)
    elif job.status == "done":
        progress = 100.0

    return JobStatusResponse(
        id=job.id,
        query=job.query,
        radiusOption=job.radius_option,
        includeUnknownLocation=job.include_unknown_location,
        status=job.status,
        progress=round(progress, 2),
        totalCandidateUrls=job.total_candidate_urls,
        processedUrls=job.processed_urls,
        foundProducts=job.found_products,
        errors=job.error_count,
        errorMessage=job.error_message,
        createdAt=job.created_at,
        updatedAt=job.updated_at,
    )


@router.post("/jobs", response_model=JobStatusResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: CreateJobRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    query_normalized = normalize_text(payload.query)
    job = Job(
        query=payload.query,
        query_normalized=query_normalized,
        radius_option=payload.radiusOption.value,
        include_unknown_location=payload.includeUnknownLocation,
        max_urls=payload.maxUrls,
        time_budget_seconds=payload.timeBudgetSeconds,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    Thread(target=process_job_inline, args=(job.id,), daemon=True).start()

    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/jobs/{job_id}/results", response_model=ResultsResponse)
def get_job_results(
    job_id: UUID,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=25, ge=1, le=500),
    productContains: str | None = Query(default=None, max_length=120),
    sizeContains: str | None = Query(default=None, max_length=80),
    priceMin: float | None = Query(default=None, ge=0),
    priceMax: float | None = Query(default=None, ge=0),
    sortBy: str = Query(default="price"),
    sortDir: str = Query(default="asc"),
    db: Session = Depends(get_db),
) -> ResultsResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    base_query = select(ProductResult).where(ProductResult.job_id == job_id)
    filters = []

    if productContains:
        filters.append(ProductResult.normalized_name.like(f"%{normalize_text(productContains)}%"))
    if sizeContains:
        filters.append(ProductResult.size_text.ilike(f"%{sizeContains}%"))
    if priceMin is not None:
        filters.append(ProductResult.price >= priceMin)
    if priceMax is not None:
        filters.append(ProductResult.price <= priceMax)
    if filters:
        base_query = base_query.where(and_(*filters))

    if sortBy == "site":
        order_column = ProductResult.domain
    else:
        order_column = ProductResult.price
    order_by = asc(order_column) if sortDir.lower() == "asc" else desc(order_column)

    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar_one()
    rows = db.execute(
        base_query.order_by(order_by).offset((page - 1) * pageSize).limit(pageSize)
    ).scalars()

    items = [
        ResultItem(
            id=row.id,
            productName=row.product_name,
            website=row.domain,
            sourceUrl=row.source_url,
            price=float(row.price) if row.price is not None else None,
            currency=row.currency,
            size=row.size_text,
            locationCity=row.location_city,
            locationAddress=row.location_address,
            distanceKm=row.distance_km,
            locationUnknown=row.location_unknown,
        )
        for row in rows
    ]

    return ResultsResponse(total=total, page=page, pageSize=pageSize, items=items)


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status)
