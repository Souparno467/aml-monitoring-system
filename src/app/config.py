from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _get_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [v.strip() for v in raw.split(",") if v.strip()]


def _normalize_db_url(url: str) -> str:
    """Normalize SQLite URLs so seed/script/server all use the same repo-root DB file."""
    if not url:
        return url
    if url.startswith("sqlite"):
        prefix = "sqlite+aiosqlite:///" if url.startswith("sqlite+aiosqlite:///") else "sqlite:///"
        if url.startswith(prefix):
            path_part = url[len(prefix):]
            # Relative paths like ./aml.db or aml.db should resolve to repo root
            if path_part.startswith("./") or ((":" not in path_part) and (not path_part.startswith("/"))):
                repo_root = Path(__file__).resolve().parents[2]
                db_path = repo_root / path_part.lstrip("./")
                return prefix + db_path.as_posix()
    return url


@dataclass(frozen=True)
class Settings:
    # App
    APP_NAME: str = "AML Monitoring System"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "dev"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = None  # type: ignore[assignment]

    # Demo helpers
    AUTO_SEED_DEMO: bool = False

    # DB / Redis
    # Default to SQLite for a zero-setup portfolio demo. Override with Postgres in production.
    DATABASE_URL: str = "sqlite+aiosqlite:///./aml.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Middleware
    RATE_LIMIT_ENABLED: bool = True

    # Rule / scoring thresholds
    LARGE_TXN_THRESHOLD_USD: float = 10_000.0
    STRUCTURING_WINDOW_MINUTES: int = 60
    STRUCTURING_COUNT_THRESHOLD: int = 3

    RISK_SCORE_MEDIUM_THRESHOLD: float = 0.40
    RISK_SCORE_HIGH_THRESHOLD: float = 0.60

    RULE_SCORE_WEIGHT: float = 0.4
    ML_SCORE_WEIGHT: float = 0.4
    GRAPH_SCORE_WEIGHT: float = 0.2

    # ML / data
    ML_MODEL_PATH: str = "src/app/ml/models"
    DATA_DIR: str = "src/aml_monitoring_system/data"


    def resolve_path(self, value: str) -> Path:
        p = Path(value)
        if p.is_absolute():
            return p
        # src/app/config.py -> repo root
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / p

    @staticmethod
    def from_env() -> "Settings":
        debug = _get_bool("DEBUG", Settings.DEBUG)
        allowed = _get_list("ALLOWED_ORIGINS", ["*"])
        # Default: disable rate limiting for local/demo (DEBUG=true), enable for prod (DEBUG=false).
        rate_limit_enabled = _get_bool("RATE_LIMIT_ENABLED", not debug)
        return Settings(
            APP_VERSION=os.getenv("APP_VERSION", Settings.APP_VERSION),
            APP_ENV=os.getenv("APP_ENV", Settings.APP_ENV),
            DEBUG=debug,
            API_PREFIX=os.getenv("API_PREFIX", Settings.API_PREFIX),
            ALLOWED_ORIGINS=allowed,
            AUTO_SEED_DEMO=_get_bool("AUTO_SEED_DEMO", Settings.AUTO_SEED_DEMO),
            DATABASE_URL=_normalize_db_url(os.getenv("DATABASE_URL", Settings.DATABASE_URL)),
            REDIS_URL=os.getenv("REDIS_URL", Settings.REDIS_URL),
            RATE_LIMIT_ENABLED=rate_limit_enabled,
            LARGE_TXN_THRESHOLD_USD=_get_float(
                "LARGE_TXN_THRESHOLD_USD", Settings.LARGE_TXN_THRESHOLD_USD
            ),
            STRUCTURING_WINDOW_MINUTES=_get_int(
                "STRUCTURING_WINDOW_MINUTES", Settings.STRUCTURING_WINDOW_MINUTES
            ),
            STRUCTURING_COUNT_THRESHOLD=_get_int(
                "STRUCTURING_COUNT_THRESHOLD", Settings.STRUCTURING_COUNT_THRESHOLD
            ),
            RISK_SCORE_MEDIUM_THRESHOLD=_get_float(
                "RISK_SCORE_MEDIUM_THRESHOLD", Settings.RISK_SCORE_MEDIUM_THRESHOLD
            ),
            RISK_SCORE_HIGH_THRESHOLD=_get_float(
                "RISK_SCORE_HIGH_THRESHOLD", Settings.RISK_SCORE_HIGH_THRESHOLD
            ),
            RULE_SCORE_WEIGHT=_get_float("RULE_SCORE_WEIGHT", Settings.RULE_SCORE_WEIGHT),
            ML_SCORE_WEIGHT=_get_float("ML_SCORE_WEIGHT", Settings.ML_SCORE_WEIGHT),
            GRAPH_SCORE_WEIGHT=_get_float("GRAPH_SCORE_WEIGHT", Settings.GRAPH_SCORE_WEIGHT),
            ML_MODEL_PATH=os.getenv("ML_MODEL_PATH", Settings.ML_MODEL_PATH),
            DATA_DIR=os.getenv("DATA_DIR", Settings.DATA_DIR),
        )


settings = Settings.from_env()





