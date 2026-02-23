import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scrapper_shared.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(String(180), nullable=False)
    query_normalized: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    radius_option: Mapped[str] = mapped_column(String(32), nullable=False)
    include_unknown_location: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_urls: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    time_budget_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)

    total_candidate_urls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_urls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    found_products: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    results: Mapped[list["ProductResult"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class ProductResult(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), index=True)

    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)

    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    size_text: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)

    location_city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    location_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    location_unknown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False, default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="results")

    __table_args__ = (
        Index("ix_results_dedupe", "normalized_name", "domain", "price"),
        Index("ix_results_source", "source_url"),
    )


class CachedUrl(Base):
    __tablename__ = "cached_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_normalized: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class CachedResult(Base):
    __tablename__ = "cached_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    query_normalized: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    size_text: Mapped[str | None] = mapped_column(String(180), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_location: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
