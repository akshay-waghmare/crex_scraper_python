"""Structlog configuration helpers for the cricket scraper."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, MutableMapping, Sequence
from contextvars import ContextVar
from typing import Any, Optional
from uuid import uuid4

import structlog

_CORRELATION_ID_VAR: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_DEFAULT_COMPONENT = "scraper"
_ALLOWED_TOP_LEVEL_KEYS = {"timestamp", "level", "correlation_id", "component", "event", "metadata"}
_IS_CONFIGURED = False

Processor = Callable[[structlog.BoundLoggerBase, str, MutableMapping[str, Any]], MutableMapping[str, Any]]


def configure_logging(
    *,
    level: int | str = logging.INFO,
    stream: Any = None,
    json_indent: Optional[int] = None,
    extra_processors: Optional[Sequence[Processor]] = None,
) -> None:
    """Configure structlog to emit JSON records with the required schema."""

    global _IS_CONFIGURED

    if _IS_CONFIGURED:
        return

    resolved_level = _resolve_log_level(level)
    target_stream = stream if stream is not None else sys.stdout

    # Use PrintLoggerFactory for tests (when stream is provided), stdlib for production
    if stream is not None:
        logger_factory = structlog.PrintLoggerFactory(file=target_stream)
    else:
        logging.basicConfig(level=resolved_level, format="%(message)s", stream=target_stream)
        logger_factory = structlog.stdlib.LoggerFactory()

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _uppercase_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _ensure_standard_schema,
    ]

    if extra_processors:
        processors.extend(extra_processors)

    processors.append(
        structlog.processors.JSONRenderer(indent=json_indent, default=_json_fallback, ensure_ascii=False)
    )

    structlog.configure(
        processors=processors,
        context_class=dict,
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )

    _IS_CONFIGURED = True


def get_logger(component: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Return a logger bound to the requested component."""

    logger = structlog.get_logger()
    component_name = component or _DEFAULT_COMPONENT

    if component_name:
        logger = logger.bind(component=component_name)

    return logger


def bind_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Bind the provided correlation identifier to the current context."""

    correlation_value = correlation_id or str(uuid4())
    _CORRELATION_ID_VAR.set(correlation_value)
    structlog.contextvars.bind_contextvars(correlation_id=correlation_value)

    return correlation_value


def clear_correlation_id() -> None:
    """Remove any correlation identifier bound to the current context."""

    _CORRELATION_ID_VAR.set(None)
    structlog.contextvars.clear_contextvars()


def _resolve_log_level(level: int | str) -> int:
    try:
        return logging._checkLevel(level)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        return logging.INFO


def _uppercase_level(_: structlog.BoundLoggerBase, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    level = event_dict.get("level")

    if isinstance(level, str):
        event_dict["level"] = level.upper()

    return event_dict


def _ensure_standard_schema(
    _: structlog.BoundLoggerBase,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Move unexpected keys into the metadata field and set defaults."""

    correlation_id = event_dict.get("correlation_id") or _CORRELATION_ID_VAR.get() or "unknown"
    event_dict["correlation_id"] = correlation_id

    component = event_dict.get("component") or _DEFAULT_COMPONENT
    event_dict["component"] = component

    metadata = event_dict.get("metadata")

    if isinstance(metadata, MutableMapping):
        metadata = dict(metadata)
    elif metadata is None:
        metadata = {}
    else:
        metadata = {"value": metadata}

    extras: dict[str, Any] = {}

    for key in list(event_dict.keys()):
        if key not in _ALLOWED_TOP_LEVEL_KEYS:
            extras[key] = event_dict.pop(key)

    if extras:
        metadata.update(extras)

    event_dict["metadata"] = metadata

    return event_dict


def _json_fallback(value: Any) -> Any:
    return repr(value)
