"""Structured JSON logging for AWS compatibility and side-effect boundaries.

Logging guidance is based on the AWS Well-Architected operational excellence pillar:
https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/observability.html
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED = set(logging.makeLogRecord({}).__dict__)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "mystack_fields", {})
        document.update(fields)
        if record.exc_info:
            document["exception"] = self.formatException(record.exc_info)
        return json.dumps(document, default=str, separators=(",", ":"), sort_keys=True)


def configure_logging(service: str, level: str | None = None) -> None:
    root = logging.getLogger()
    resolved_level = (level or os.getenv("MYSTACK_LOG_LEVEL", "INFO")).upper()
    root.setLevel(resolved_level)
    if not any(getattr(handler, "mystack_json", False) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        handler.mystack_json = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    log_event(
        logging.getLogger(__name__),
        logging.INFO,
        "observability.configured",
        service=service,
        log_level=resolved_level,
        sensitive_fields_policy="authorization and payload contents are never logged",
    )


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    safe_fields = {key: value for key, value in fields.items() if key not in _RESERVED}
    logger.log(level, event, extra={"mystack_fields": safe_fields}, exc_info=exc_info)


def payload_fingerprint(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]
