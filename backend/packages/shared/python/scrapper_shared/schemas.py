from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from scrapper_shared.enums import RadiusOption


class CreateJobRequest(BaseModel):
    query: str = Field(min_length=2, max_length=180)
    radiusOption: RadiusOption
    includeUnknownLocation: bool = False
    maxUrls: int = Field(default=80, ge=20, le=200)
    timeBudgetSeconds: int = Field(default=90, ge=60, le=180)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Query cannot be blank")
        return cleaned


class JobStatusResponse(BaseModel):
    id: UUID
    query: str
    radiusOption: str
    includeUnknownLocation: bool
    status: str
    progress: float
    totalCandidateUrls: int
    processedUrls: int
    foundProducts: int
    errors: int
    errorMessage: str | None = None
    createdAt: datetime
    updatedAt: datetime


class ResultItem(BaseModel):
    id: UUID
    productName: str
    website: str
    sourceUrl: str
    price: float | None
    currency: str | None
    size: str | None
    locationCity: str | None
    locationAddress: str | None
    distanceKm: float | None
    locationUnknown: bool


class ResultsResponse(BaseModel):
    total: int
    page: int
    pageSize: int
    items: list[ResultItem]


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
