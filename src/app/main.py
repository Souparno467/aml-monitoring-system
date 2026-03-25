from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import router as v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import init_db
from app.utils.seed import ensure_seeded_if_empty
from app.middleware import AccessLogMiddleware, RateLimitMiddleware, RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    try:
        await ensure_seeded_if_empty()
    except Exception:
        # Demo helper should never break app startup
        pass
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

register_exception_handlers(app)
app.include_router(v1_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}

