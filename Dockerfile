FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

# For xgboost runtime (OpenMP)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Minimal runtime deps (keep simple for fresher-level deployment)
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy asyncpg aiosqlite pydantic python-jose bcrypt redis celery httpx pytest pytest-asyncio pandas scikit-learn joblib networkx xgboost

ENV PYTHONPATH=/app/src

EXPOSE 8000

# Render (and many PaaS) provides a $PORT env var. Default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
