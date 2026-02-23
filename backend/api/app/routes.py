from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.exceptions import RedisError
from sqlalchemy import and_, asc, desc, func, select, text
from sqlalchemy.orm import Session

from scrapper_shared.config import get_settings
from scrapper_shared.database import get_db
from scrapper_shared.models import Job, ProductResult
from scrapper_shared.normalization import normalize_text
from scrapper_shared.queue import get_queue, get_redis
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
def create_job(payload: CreateJobRequest, request: Request, db: Session = Depends(get_db)) -> JobStatusResponse:
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

    try:
        queue = get_queue()
        queue.enqueue("worker.jobs.process_job", str(job.id), job_timeout=payload.timeBudgetSeconds + 180)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = f"Queue unavailable: {exc}"
        db.commit()
        raise HTTPException(status_code=503, detail="Queue unavailable. Try again shortly.") from exc

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
    redis_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    try:
        get_redis().ping()
    except RedisError:
        redis_status = "down"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, redis=redis_status)
