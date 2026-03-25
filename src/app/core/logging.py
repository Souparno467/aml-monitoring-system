from __future__ import annotations

import logging
from typing import Any


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_logger(name: str) -> Any:
    try:
        import structlog  # type: ignore

        return structlog.get_logger(name)
    except Exception:
        return logging.getLogger(name)

