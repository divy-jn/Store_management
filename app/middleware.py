"""
Structured logging middleware for the Store Intelligence API.
Logs trace_id, store_id, endpoint, latency_ms, event_count, status_code per request.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ─────────────────────────────────────────────
# Configure structlog for JSON output
# ─────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ─────────────────────────────────────────────
# Request Logging Middleware
# ─────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs structured request/response data.

    For every request, logs:
    - trace_id: UUID per request for distributed tracing
    - store_id: extracted from URL path if present
    - endpoint: request path
    - method: HTTP method
    - latency_ms: request duration in milliseconds
    - event_count: number of events (for POST /events/ingest)
    - status_code: HTTP response status
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        # Extract store_id from path if present
        store_id = self._extract_store_id(request.url.path)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Build log context
            log_data = {
                "trace_id": trace_id,
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
            }

            if store_id:
                log_data["store_id"] = store_id

            # Log event count for ingest endpoint
            if request.url.path == "/events/ingest" and request.method == "POST":
                event_count = getattr(request.state, "event_count", None)
                if event_count is not None:
                    log_data["event_count"] = event_count

            # Choose log level based on status code
            if response.status_code >= 500:
                logger.error("request_completed", **log_data)
            elif response.status_code >= 400:
                logger.warning("request_completed", **log_data)
            else:
                logger.info("request_completed", **log_data)

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id
            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                trace_id=trace_id,
                method=request.method,
                endpoint=request.url.path,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
                store_id=store_id,
            )
            raise

    @staticmethod
    def _extract_store_id(path: str) -> str | None:
        """Extract store_id from URL path like /stores/{store_id}/metrics."""
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "stores":
            return parts[1]
        return None
