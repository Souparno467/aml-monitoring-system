# Anti Money Laundering (AML) Monitoring Demo

Portfolio-ready AML monitoring system with a FastAPI backend and a React analyst console.

## Stack

- Backend: FastAPI + SQLAlchemy (async) + Alembic
- DB: SQLite by default (easy demo); can be swapped to Postgres later
- ML: scikit-learn + XGBoost (joblib saved model)
- Async pipeline (demo): Celery + Redis
- UI: React (Vite)

## Deployment (planned)

This is currently a local-first portfolio demo. A public deployment is planned for a future iteration (containerized API + hosted frontend + managed Postgres), and this README will be updated when that’s ready.

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
