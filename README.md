# API Health & Incident Monitor

A FastAPI service that polls registered HTTP endpoints every 5 minutes, records status codes, response times and failure details in MongoDB, and tracks incidents (opened on first failure, updated on repeated failures, resolved on recovery).

**Stack:** Python 3.12 · FastAPI · Motor (async MongoDB) · httpx · Azure Cosmos DB for MongoDB · Azure Container Apps · Docker · GitHub Actions

## How it works

```
POST /services ──► MongoDB `services`
                        │
   background poller (every 5 min, concurrent via asyncio.gather)
                        │
        check_service() ─► status code, latency, error
                        │
        ├─► `checks`     (every result, kept for history)
        └─► `incidents`  (open → failure_count++ → resolved)
                        │
GET /incidents ◄────────┘
```

A check **fails** when the request errors (timeout / connection), the status differs from `expected_status`, or latency exceeds `LATENCY_THRESHOLD_MS`.

## API

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/services` | Register a service `{name, url, expected_status?}`. Validates URL, returns 422 on bad input and 409 on a duplicate URL. |
| GET | `/services` | List services with last check time and up/down status. |
| GET | `/incidents` | Incident history, newest first. Query params: `service_id`, `status` (`open`/`resolved`), `limit` (1-200). |
| GET | `/health` | Liveness probe. |

Interactive docs at `/docs` (Swagger UI).

## Run locally

### Option A: Docker (easiest)
```bash
docker compose up --build
python scripts/seed.py http://localhost:8000   # registers 4 demo endpoints
```
Open http://localhost:8000/docs

### Option B: Python venv + local MongoDB
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # edit MONGODB_URI if needed
uvicorn app.main:app --reload
```
Tip: for a quick demo set `POLL_INTERVAL_SECONDS=20` in `.env`.

## Tests
```bash
pytest -q
```
6 unit tests (no real network or MongoDB needed; uses `httpx.MockTransport` and `mongomock-motor`):
success check, 5xx failure, timeout handling, no duplicate incidents on repeated failures, incident resolution on recovery, and request validation / duplicate rejection.

## Deploy to Azure

Prereqs: [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), `az login`, an Azure subscription (the free account works).

```bash
bash deploy/azure_deploy.sh
```
This creates a resource group, **Cosmos DB for MongoDB** (free tier), **Azure Container Registry** (image built in the cloud, no local Docker required) and an **Azure Container App** pinned to exactly 1 replica so the poller runs once and never scales to zero. The Mongo connection string is stored as a Container Apps secret.

Delete everything when finished to avoid charges:
```bash
az group delete -n rg-health-monitor --yes --no-wait
```

### CI/CD (optional)
`.github/workflows/deploy.yml` runs the tests on every push and redeploys on `main`. Add these repo secrets: `AZURE_CREDENTIALS` (output of `az ad sp create-for-rbac --sdk-auth`), `ACR_NAME`, `APP_NAME`, `RESOURCE_GROUP`.

### Using MongoDB Atlas instead of Cosmos DB
Skip the Cosmos block in the script and set `MONGODB_URI` to your Atlas `mongodb+srv://...` string.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017` | Mongo connection string |
| `MONGODB_DB` | `health_monitor` | Database name |
| `POLL_INTERVAL_SECONDS` | `300` | Polling interval (5 min) |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `LATENCY_THRESHOLD_MS` | `2000` | Slower than this counts as a failure |
| `LOG_LEVEL` | `INFO` | Structured JSON logs to stdout |
| `ENABLE_POLLER` | `true` | Disable to run API only |

## Project layout
```
app/        config, logging, models, db, checker, poller, routes, main
tests/      6 unit tests
scripts/    seed.py (registers 4 demo endpoints)
deploy/     azure_deploy.sh
```

## Extending
Alerting (email/Teams webhook on incident open), a `/services/{id}/checks` history route, auth, and a dashboard are natural next steps.
