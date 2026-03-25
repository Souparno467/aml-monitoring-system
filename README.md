# Anti Money Laundering (AML) Monitoring Demo

Portfolio-ready AML monitoring system with a FastAPI backend and a React analyst console.

## Stack

- Backend: FastAPI + SQLAlchemy (async) + Alembic
- DB: SQLite by default (easy demo); can be swapped to Postgres later
- ML: scikit-learn + XGBoost (joblib saved model)
- Async pipeline (demo): Celery + Redis
- UI: React (Vite)

## Run (recommended)

This starts **API + Celery worker + Redis**:

```bash
cp .env.example .env  # macOS/Linux
# or (PowerShell)
Copy-Item .env.example .env

docker compose up --build
```

API: `http://localhost:8000/api/v1`  
Swagger: `http://localhost:8000/docs`

## Docker (production-style)

Builds and runs **API + Celery worker + Redis + Nginx (serving the React build)**:

```bash
cp .env.example .env  # macOS/Linux
# or (PowerShell)
Copy-Item .env.example .env

# recommended for production-style runs
docker compose -f docker-compose.prod.yml up --build
```

Frontend (Nginx): `http://localhost:8080`  
API (proxied): `http://localhost:8080/api/v1`

For a real deployment, set `DEBUG=false` and use Postgres instead of SQLite.

## Deploy (Render + Vercel)

This repo includes `render.yaml` to deploy:
- Render: API (web) + Celery worker + Redis
- Vercel: frontend (Vite)

Render:
- Create a new Render Blueprint from this repo (it will pick up `render.yaml`).
- Set `ALLOWED_ORIGINS` to your Vercel URL (and keep `DEBUG=false`).
- (Recommended) add Postgres and set `DATABASE_URL` so data persists.

Vercel:
- Import the `frontend/` project.
- Set env var `VITE_API_BASE_URL` to `https://<your-render-api>/api/v1`.

## Run locally (no Docker)

If your project uses a `src/` layout, the simplest command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src
```

If you want the async demo endpoints (`/transactions/async`), you also need Redis + a Celery worker:

```bash
# terminal 1: redis (or run via docker)
redis-server

# terminal 2: celery worker
# Run from the `src/` directory so imports resolve correctly:
cd src

# On Windows, use the `solo` pool (prefork isn't supported).
celery -A app.workers.celery_worker:celery_app worker --loglevel=info -Q transactions,alerts -P solo
```

## Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173` (proxies `/api/*` to the backend).

Optional `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

When running the production-style Docker stack (`docker-compose.prod.yml`), **do not** set `VITE_API_BASE_URL` to `http://localhost:8000/...` unless you also publish the API port. The Docker frontend is served from `http://localhost:8080` and expects same-origin API requests via `/api/v1`.

## Demo Script (end-to-end)

Use this sequence in an interview to show the full workflow:

### 1) Seed demo data

Seeds DB tables from CSVs in `settings.DATA_DIR` (DEBUG-only endpoint):

```bash
curl -X POST "http://localhost:8000/api/v1/dashboard/seed?reset=true"
```

Then confirm counts:

```bash
curl "http://localhost:8000/api/v1/dashboard/status"
```

### 2) Train (time-based split: train older, test newer)

Train a model using a **time split** (default):

```bash
curl -X POST "http://localhost:8000/api/v1/risk/model/train"   -H "Content-Type: application/json"   -d '{"max_rows":50000,"test_size":0.2,"random_state":42,"split_strategy":"time"}'
```

### 3) Evaluate

Shows ROC-AUC / Average Precision + top risky examples:

```bash
curl -X POST "http://localhost:8000/api/v1/risk/evaluate"   -H "Content-Type: application/json"   -d '{"max_rows":50000,"top_n":10}'
```

### 4) Create a transaction (sync)

```bash
curl -X POST "http://localhost:8000/api/v1/transactions"   -H "Content-Type: application/json"   -d '{
    "txn_id":"TXN-DEMO-0001",
    "sender_id":"USR00070",
    "receiver_id":"USR00057",
    "amount_usd":12000,
    "amount_local":12000,
    "currency":"USD",
    "fx_rate_to_usd":1,
    "payment_method":"bank_transfer",
    "txn_type":"wire",
    "timestamp":"2026-03-25T12:00:00Z",
    "is_cross_border":true,
    "sender_country":"CU",
    "receiver_country":"US",
    "ip_country":"US",
    "channel":"api"
  }'
```

Explain the score (human-readable reasons + highlights):

```bash
curl "http://localhost:8000/api/v1/transactions/TXN-DEMO-0001/explain"
```

### 5) Create a transaction (async pipeline)

Queue to Celery (requires Redis + worker running):

```bash
curl -X POST "http://localhost:8000/api/v1/transactions/async"   -H "Content-Type: application/json"   -d '{"txn_id":"TXN-DEMO-ASYNC-0001", "sender_id":"USR00070", "receiver_id":"USR00057", "amount_usd":9000, "amount_local":9000, "currency":"USD", "fx_rate_to_usd":1, "timestamp":"2026-03-25T12:05:00Z", "is_cross_border":true}'
```

Poll task status:

```bash
curl "http://localhost:8000/api/v1/transactions/tasks/<TASK_ID>"
```

### 6) See alerts ? triage ? audit log increments

- UI: open **Alerts** page, filter by severity/user, select an alert
- Click **Save** / **Escalate** to create audit log entries
- UI: return to **Dashboard** and click **Refresh** to see **Audit Logs** count increment

Explain an alert:

```bash
curl "http://localhost:8000/api/v1/alerts/<ALERT_ID>/explain"
```
