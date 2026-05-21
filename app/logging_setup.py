from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

try:  # orjson is the prod dependency; fall back to stdlib json if it's absent.
    import orjson

    def _json_serializer(obj: Any, **_: Any) -> str:
        # orjson serializes datetime/UUID natively; default=str catches the rest.
        return orjson.dumps(obj, default=str).decode("utf-8")
except ModuleNotFoundError:  # pragma: no cover - depends on env
    import json

    def _json_serializer(obj: Any, **_: Any) -> str:
        return json.dumps(obj, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure structlog + stdlib logging as one pipeline writing to stdout.

    - All logs (ours, aiogram, sqlalchemy, asyncpg) flow through the same renderer.
    - `fmt="json"` → one JSON object per line (for prod log aggregation).
    - `fmt="console"` → coloured human-readable output (for local dev).
    - Per-update context (uid / chat / update_id) is merged in via contextvars,
      bound by LoggingContextMiddleware.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # structlog-native loggers hand their event dict to the stdlib formatter.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if fmt.lower() == "console":
        renderer: Any = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    else:
        renderer = structlog.processors.JSONRenderer(serializer=_json_serializer)

    formatter = structlog.stdlib.ProcessorFormatter(
        # foreign_pre_chain processes records emitted by plain stdlib loggers
        # (aiogram, sqlalchemy, ...) so they get the same shape as ours.
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Tame third-party noise so prod logs stay readable.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
