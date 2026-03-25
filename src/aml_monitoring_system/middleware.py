"""
Middleware Stack
----------------
Three middleware classes registered in main.py:

1. RequestIDMiddleware   — injects a unique X-Request-ID into every request
                           and response, binds it to structlog context so all
                           log lines for a request share the same ID.

2. AccessLogMiddleware   — structured JSON log line per request with method,
                           path, status, duration, user_id (if authenticated).

3. RateLimitMiddleware   — sliding-window rate limiter backed by Redis.
                           Configurable per-route tier: default / strict / open.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

import redis.asyncio as aioredis
import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = structlog.get_logger(__name__)


# ── 1. Request ID Middleware ──────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attaches a UUID4 request ID to every request.
    - Reads  X-Request-ID header if the client supplies one (useful for tracing
      across services / mobile apps).
    - Falls back to generating a new UUID.
    - Binds the ID to structlog context so every log line within the request
      automatically includes it.
    - Echoes the ID back in the response header.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind to structlog context for this async task
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Expose via request state so route handlers can read it
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── 2. Access Log Middleware ──────────────────────────────────────────────────

class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Emits one structured log line per HTTP request containing:
      method, path, status_code, duration_ms, user_id (from JWT if present),
      ip, user_agent, request_id.

    Skips /health and /docs to avoid noise.
    """

    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Extract user from state if auth middleware already parsed it
        user_id = getattr(request.state, "user_id", None)

        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "http_request",
            method      = request.method,
            path        = request.url.path,
            status_code = response.status_code,
            duration_ms = duration_ms,
            user_id     = user_id,
            ip          = _get_client_ip(request),
            user_agent  = request.headers.get("User-Agent", "")[:100],
            request_id  = getattr(request.state, "request_id", None),
        )
        return response


# ── 3. Rate Limit Middleware ──────────────────────────────────────────────────

# Route-tier configuration: (max_requests, window_seconds)
_RATE_LIMIT_TIERS: dict[str, tuple[int, int]] = {
    "strict"  : (20,   60),    # e.g. /login — 20 req/min
    "default" : (200,  60),    # standard API endpoints — 200 req/min
    "open"    : (1000, 60),    # health / docs
}

# Path prefix → tier mapping
_PATH_TIERS: dict[str, str] = {
    "/api/v1/users/login"   : "strict",
    "/health"               : "open",
    "/docs"                 : "open",
    "/redoc"                : "open",
}


def _tier_for_path(path: str) -> str:
    for prefix, tier in _PATH_TIERS.items():
        if path.startswith(prefix):
            return tier
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter using Redis INCR + EXPIRE.

    Key format:  rl:{ip}:{path_tier}:{window_bucket}
    Falls back gracefully if Redis is unavailable — never blocks requests.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
                )
            except Exception:
                return None
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        r = await self._get_redis()
        if r is None:
            # Redis unavailable — fail open
            return await call_next(request)

        tier          = _tier_for_path(request.url.path)
        max_req, window = _RATE_LIMIT_TIERS[tier]
        client_ip     = _get_client_ip(request) or "unknown"
        bucket        = int(time.time()) // window
        key           = f"rl:{client_ip}:{tier}:{bucket}"

        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window)

            # Attach rate limit headers to every response
            remaining = max(0, max_req - count)
            reset_at  = (bucket + 1) * window

            if count > max_req:
                logger.warning(
                    "Rate limit exceeded",
                    ip=client_ip, path=request.url.path, count=count, limit=max_req,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Too many requests. Please slow down.", "retry_after": window},
                    headers={
                        "X-RateLimit-Limit"    : str(max_req),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset"    : str(reset_at),
                        "Retry-After"          : str(window),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"]     = str(max_req)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"]     = str(reset_at)
            return response

        except Exception as exc:
            logger.warning("Rate limiter error, failing open", error=str(exc))
            return await call_next(request)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", None)
