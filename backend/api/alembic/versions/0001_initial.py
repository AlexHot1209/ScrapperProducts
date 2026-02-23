"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(length=180), nullable=False),
        sa.Column("query_normalized", sa.String(length=180), nullable=False),
        sa.Column("radius_option", sa.String(length=32), nullable=False),
        sa.Column("include_unknown_location", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_urls", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("total_candidate_urls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_urls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("found_products", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_query_normalized", "jobs", ["query_normalized"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("size_text", sa.String(length=180), nullable=True),
        sa.Column("location_city", sa.String(length=120), nullable=True),
        sa.Column("location_address", sa.String(length=500), nullable=True),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lon", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("location_unknown", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extraction_method", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_results_job_id", "results", ["job_id"])
    op.create_index("ix_results_domain", "results", ["domain"])
    op.create_index("ix_results_price", "results", ["price"])
    op.create_index("ix_results_size_text", "results", ["size_text"])
    op.create_index("ix_results_location_city", "results", ["location_city"])
    op.create_index("ix_results_distance_km", "results", ["distance_km"])
    op.create_index("ix_results_location_unknown", "results", ["location_unknown"])
    op.create_index("ix_results_source", "results", ["source_url"])
    op.create_index("ix_results_dedupe", "results", ["normalized_name", "domain", "price"])

    op.create_table(
        "cached_urls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_normalized", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cached_urls_query_normalized", "cached_urls", ["query_normalized"])
    op.create_index("ix_cached_urls_expires_at", "cached_urls", ["expires_at"])

    op.create_table(
        "cached_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.String(length=80), nullable=False),
        sa.Column("query_normalized", sa.String(length=180), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("size_text", sa.String(length=180), nullable=True),
        sa.Column("location_city", sa.String(length=120), nullable=True),
        sa.Column("location_address", sa.String(length=500), nullable=True),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lon", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cache_key"),
    )
    op.create_index("ix_cached_results_cache_key", "cached_results", ["cache_key"])
    op.create_index("ix_cached_results_query_normalized", "cached_results", ["query_normalized"])
    op.create_index("ix_cached_results_domain", "cached_results", ["domain"])
    op.create_index("ix_cached_results_expires_at", "cached_results", ["expires_at"])

    op.create_table(
        "geocode_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("raw_location", sa.String(length=500), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("raw_location"),
    )
    op.create_index("ix_geocode_cache_raw_location", "geocode_cache", ["raw_location"])


def downgrade() -> None:
    op.drop_index("ix_geocode_cache_raw_location", table_name="geocode_cache")
    op.drop_table("geocode_cache")

    op.drop_index("ix_cached_results_expires_at", table_name="cached_results")
    op.drop_index("ix_cached_results_domain", table_name="cached_results")
    op.drop_index("ix_cached_results_query_normalized", table_name="cached_results")
    op.drop_index("ix_cached_results_cache_key", table_name="cached_results")
    op.drop_table("cached_results")

    op.drop_index("ix_cached_urls_expires_at", table_name="cached_urls")
    op.drop_index("ix_cached_urls_query_normalized", table_name="cached_urls")
    op.drop_table("cached_urls")

    op.drop_index("ix_results_dedupe", table_name="results")
    op.drop_index("ix_results_source", table_name="results")
    op.drop_index("ix_results_location_unknown", table_name="results")
    op.drop_index("ix_results_distance_km", table_name="results")
    op.drop_index("ix_results_location_city", table_name="results")
    op.drop_index("ix_results_size_text", table_name="results")
    op.drop_index("ix_results_price", table_name="results")
    op.drop_index("ix_results_domain", table_name="results")
    op.drop_index("ix_results_job_id", table_name="results")
    op.drop_table("results")

    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_query_normalized", table_name="jobs")
    op.drop_table("jobs")
