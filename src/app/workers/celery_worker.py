from __future__ import annotations

import os

try:
    from celery import Celery
except Exception:  # pragma: no cover
    Celery = None


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if Celery is not None:
    celery_app = Celery(
        "aml_worker",
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["app.workers.tasks"],
    )
    celery_app.conf.task_routes = {
        "app.workers.tasks.ingest_transaction": {"queue": "transactions"},
        "app.workers.tasks.process_transaction": {"queue": "transactions"},
        "app.workers.tasks.run_batch_risk_checks": {"queue": "transactions"},
        "app.workers.tasks.generate_alerts": {"queue": "alerts"},
    }
else:
    celery_app = None
