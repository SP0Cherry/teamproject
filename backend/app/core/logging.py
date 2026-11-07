import json
import logging
import sys
import uuid

import structlog


def get_request_id() -> str:
    return str(uuid.uuid4())


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def bind_request_id(request_id: str) -> None:
    """Bind request_id to structlog contextvars for all subsequent logs."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)
