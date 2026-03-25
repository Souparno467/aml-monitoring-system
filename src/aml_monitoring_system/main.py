from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import structlog

from app.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import register_exception_handlers
from app.db.session import init_db
from app.api.v1 import transactions, alerts, users, risk, pep, dashboard

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    logger.info("AML Monitoring System started", version=settings.APP_VERSION, env=settings.APP_ENV)
    yield
    logger.info("AML Monitoring System shutting down")


app = FastAPI(
    title="AML Monitoring System",
    description="Production-grade Anti-Money Laundering monitoring API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# â”€â”€ Middleware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# â”€â”€ Exception Handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
register_exception_handlers(app)

# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PREFIX = settings.API_PREFIX

app.include_router(transactions.router, prefix=f"{PREFIX}/transactions", tags=["Transactions"])
app.include_router(alerts.router,       prefix=f"{PREFIX}/alerts",       tags=["Alerts"])
app.include_router(users.router,        prefix=f"{PREFIX}/users",         tags=["Users"])
app.include_router(risk.router,         prefix=f"{PREFIX}/risk",          tags=["Risk Engine"])
app.include_router(pep.router,          prefix=f"{PREFIX}/pep",           tags=["PEP"])
app.include_router(dashboard.router,    prefix=f"{PREFIX}/dashboard",     tags=["Dashboard"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}

