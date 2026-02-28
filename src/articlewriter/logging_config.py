"""
Structured logging for the pipeline. Writes to console and optional file.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog


def configure_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure structlog and stdlib logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.processors.CallsiteParameterAdder()],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(log_level)
        root = logging.getLogger()
        root.addHandler(fh)
