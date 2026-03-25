from __future__ import annotations

import json
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_IS_STRUCTLOG = hasattr(logger, "bind") or logger.__class__.__module__.startswith("structlog")


def _emit_log(level: str, event: str, **fields) -> None:
    """Emit structured log if structlog is available; otherwise JSON-stringify."""
    if _IS_STRUCTLOG:
        log_fn = getattr(logger, level, None)
        if callable(log_fn):
            log_fn(event, **fields)
        return

    log_fn = getattr(logger, level, None)
    if callable(log_fn):
        log_fn("%s %s", event, json.dumps(fields, default=str, ensure_ascii=False))


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return await call_next(request)

        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        user_id = getattr(request.state, "user_id", None)

        _emit_log(
            "warning" if response.status_code >= 400 else "info",
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            request_id=getattr(request.state, "request_id", None),
        )
        return response


_RATE_LIMIT_TIERS: dict[str, tuple[int, int]] = {
    "strict": (20, 60),
    "default": (200, 60),
    "open": (1000, 60),
}

_PATH_TIERS: dict[str, str] = {
    "/health": "open",
    "/docs": "open",
    "/redoc": "open",
}


def _tier_for_path(path: str) -> str:
    for prefix, tier in _PATH_TIERS.items():
        if path.startswith(prefix):
            return tier
    return "default"


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._redis = None
        self._redis_failed = False

    async def _get_redis(self):
        if self._redis_failed:
            return None
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis  # type: ignore

            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            await r.ping()
            self._redis = r
        except Exception:
            self._redis = None
            self._redis_failed = True

        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return await call_next(request)

        r = await self._get_redis()
        if r is None:
            return await call_next(request)

        tier = _tier_for_path(request.url.path)
        max_req, window = _RATE_LIMIT_TIERS[tier]
        client_ip = _get_client_ip(request) or "unknown"
        bucket = int(time.time()) // window
        key = f"rl:{client_ip}:{tier}:{bucket}"

        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window)

            remaining = max(0, max_req - count)
            reset_at = (bucket + 1) * window

            if count > max_req:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Too many requests. Please slow down.", "retry_after": window},
                    headers={
                        "X-RateLimit-Limit": str(max_req),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_at),
                        "Retry-After": str(window),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_req)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)
            return response
        except Exception:
            # If Redis is down/misconfigured, disable rate limiting (fail open).
            self._redis = None
            self._redis_failed = True
            return await call_next(request)

