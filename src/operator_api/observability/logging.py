from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with rich operational context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request tracing metadata if present
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            log_entry["request_id"] = str(request_id)

        client_ip = getattr(record, "client_ip", None)
        if client_ip is not None:
            log_entry["client_ip"] = str(client_ip)

        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_entry["duration_ms"] = float(duration_ms)

        # Attach exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)
