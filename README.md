# Romania Product Discovery Scraper

Production-ready monorepo with:
- `frontend`: Next.js + Tailwind single-page UI
- `backend/api`: FastAPI REST API + orchestration
- `backend/packages/shared/python`: shared models, schemas, discovery, scraping, normalization, location logic
- `docker-compose.yml`: local full stack (web + api + postgres)

## Features
- Background jobs with polling:
  - `POST /api/jobs`
  - `GET /api/jobs/{id}`
  - `GET /api/jobs/{id}/results`
  - `GET /api/health`
- Search discovery via supported APIs only:
  - Google Programmable Search (CSE JSON API), or
  - SerpAPI (`SEARCH_PROVIDER=serpapi`)
- Extraction priority:
  1. JSON-LD schema.org Product
  2. Microdata
  3. OpenGraph/meta
  4. Heuristic visible text regex (`lei`/`RON`, size patterns)
- Polite crawling:
  - robots.txt checks where feasible
  - domain-aware throttling + jitter
  - retries/backoff for transient errors (429/503)
  - explicit user-agent
  - no login/captcha/paywall bypass logic
- Location + radius filtering from Bucuresti:
  - `Bucuresti` (15km strict)
  - `50`, `100`, `200` km
  - `All Romania`
- Unknown location behavior:
  - Controlled by `includeUnknownLocation`
  - UI defaults OFF for `Bucuresti`, ON for larger radii/all Romania
- Caching:
  - discovered URLs by normalized query + provider
  - parsed results by query+URL cache key
  - geocode cache
- Dedupe:
  - `(normalized_name + domain + price)`
  - canonical/source URL key
- Client-side result filtering and sorting + CSV export.

## Monorepo Structure
```text
frontend/
backend/
  api/
  packages/
    shared/
      python/
      types/
  infra/
docker-compose.yml
```

## Environment Variables
Copy `.env.example` to `.env` and fill required values.

Performance tuning (optional):
- `SCRAPER_CONCURRENCY` (default: `6`)
- `SCRAPE_BATCH_SIZE` (default: `25`)
- `HTTP_MAX_CONNECTIONS` (default: `100`)
- `HTTP_MAX_KEEPALIVE_CONNECTIONS` (default: `40`)
- `FETCH_CACHE_TTL_SECONDS` (default: `600`)

Required for discovery:
- Google CSE:
  - `SEARCH_PROVIDER=google`
  - `GOOGLE_CSE_API_KEY`
  - `GOOGLE_CSE_CX`
- or SerpAPI:
  - `SEARCH_PROVIDER=serpapi`
  - `SERPAPI_API_KEY`
- or Manual (allowlist):
  - `SEARCH_PROVIDER=manual`
  - `ALLOWED_DOMAINS` (comma-separated domains)

## Local Run
1. Copy env file:
   - `cp .env.example .env` (or PowerShell equivalent)
2. Fill search API keys in `.env`.
3. Start stack:
   - `docker compose up --build`
4. Open:
   - Web: `http://localhost:3000`
   - API health: `http://localhost:8000/api/health`

The API container runs Alembic migrations on startup.

## API Contract

### `POST /api/jobs`
Body:
```json
{
  "query": "trandafir catarator",
  "radiusOption": "100",
  "includeUnknownLocation": true,
  "maxUrls": 80,
  "timeBudgetSeconds": 90
}
```

### `GET /api/jobs/{id}`
Returns status (`queued|running|done|failed`) and progress counters:
- `totalCandidateUrls`
- `processedUrls`
- `foundProducts`
- `errors`

### `GET /api/jobs/{id}/results`
Paged results with:
- `productName`
- `website`
- `sourceUrl`
- `price`
- `currency`
- `size`
- `locationCity`
- `distanceKm`
- `locationUnknown`

## Frontend
Single route `/` with:
- query form
- radius selector
- include unknown location toggle
- max sites + time budget controls
- live progress bar + counters
- results table (Product, Website, Price, Size, Location, Link)
- client filters (name contains, size contains, min/max price)
- sorting (price, site)
- CSV export
- loading/error/empty states

## Linting / Formatting
- Python: `black`, `isort`, `ruff` (configured in root `pyproject.toml`)
- TypeScript: `eslint`, `prettier`

## Tests
Unit tests are included for:
- extraction from JSON-LD / OpenGraph fallback
- text normalization and Romanian price/size parsing

Run API tests in container or local venv:
- `pytest backend/api/tests`

## Deployment

### Web (Vercel or Netlify)
1. Deploy `frontend`.
2. Set `NEXT_PUBLIC_API_BASE_URL` to the deployed API URL.
3. Build command: `npm --workspace frontend run build`
4. Start command: `npm --workspace frontend run start`

### API (Render concrete walkthrough)
1. Push this repo to GitHub.
2. In Render, create resources from `backend/infra/render.yaml` (Blueprint).
3. Add secrets:
   - `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX` (or `SERPAPI_API_KEY`)
4. Confirm `DATABASE_URL` is wired from your database.
5. Deploy:
   - Web Service: API (`backend/api/Dockerfile`)
6. Run migrations:
   - API startup command already applies `alembic upgrade head`.

## Limitations / ToS / Legal Notes
- This project intentionally does not scrape Google Search HTML.
- It depends on official search APIs (Google CSE JSON API or SerpAPI).
- robots.txt compliance is best-effort and not a legal guarantee.
- Site terms of service vary by domain and must be reviewed before production use.
- Geocoding uses Nominatim (OSM); usage limits apply. Keep caching enabled.
- Dynamic sites that block all automation may still fail.
