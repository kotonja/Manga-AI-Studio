from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from manga_api.config import Settings


REQUEST_ID_HEADER = "X-Request-ID"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ["request_id", "job_id", "project_id", "page_id", "panel_id", "provider", "status_code", "duration_ms"]:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.logger = logging.getLogger("manga_api.request")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            status_code = response.status_code if response is not None else 500
            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id
            self.logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_request_bytes: int) -> None:
        super().__init__(app)
        self.max_request_bytes = max_request_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                length = 0
            if self.max_request_bytes > 0 and length > self.max_request_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": "Request body is too large",
                        "max_request_bytes": self.max_request_bytes,
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small per-process placeholder limiter for production wiring.

    It is intentionally disabled by default. Real deployments should put a shared
    limiter at the edge or back it with Redis before enabling multi-replica APIs.
    """

    def __init__(self, app, enabled: bool, per_minute: int) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.per_minute = per_minute
        self.window_seconds = 60
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or self.per_minute <= 0:
            response = await call_next(request)
            response.headers.setdefault("X-RateLimit-Policy", "disabled")
            return response

        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        bucket = self.requests[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "request_id": getattr(request.state, "request_id", None),
                },
                headers={"Retry-After": "60", "X-RateLimit-Policy": f"{self.per_minute}/minute"},
            )
        bucket.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Policy"] = f"{self.per_minute}/minute"
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.per_minute - len(bucket)))
        return response


def request_id_from_request(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
