from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.operator_api.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
)

logger = logging.getLogger("src.operator_api.access")


class RequestTraceMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware providing request tracing, timing, metrics, and structured access logging.

    Features:
    - Generates or propagates `X-Request-ID` header.
    - Measures request duration and attaches `X-Response-Time-Ms` header.
    - Automatically updates MetricsCollector.
    - Emits structured JSON access log for every completed or failed request.
    """

    def __init__(
        self,
        app: Any,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        super().__init__(app)
        self._metrics = metrics_collector or get_metrics_collector()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        client_ip = request.client.host if request.client else "unknown"

        # Track in-flight request
        self._metrics.record_request_start()
        start_time = time.perf_counter()

        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration_sec = time.perf_counter() - start_time
            duration_ms = round(duration_sec * 1000.0, 2)
            self._metrics.record_request_complete(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_sec=duration_sec,
            )
            logger.error(
                f"{request.method} {request.url.path} 500 - {duration_ms}ms",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "duration_ms": duration_ms,
                },
                exc_info=exc,
            )
            raise exc
        else:
            duration_sec = time.perf_counter() - start_time
            duration_ms = round(duration_sec * 1000.0, 2)
            self._metrics.record_request_complete(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_sec=duration_sec,
            )

            # Attach tracing headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

            # Emit structured access log
            logger.info(
                f"{request.method} {request.url.path} {status_code} - {duration_ms}ms",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "duration_ms": duration_ms,
                },
            )
            return response
