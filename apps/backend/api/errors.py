"""Consistent API errors and request correlation for local/team diagnostics."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

LOGGER = logging.getLogger("reporter.api")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def install_error_handling(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = normalized_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started_at = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        LOGGER.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def normalized_request_id(candidate: str | None) -> str:
    value = (candidate or "").strip()
    return value if _SAFE_REQUEST_ID.fullmatch(value) else uuid.uuid4().hex


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ."
    return _error_response(
        request,
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        detail=detail,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        detail="Dữ liệu gửi lên không hợp lệ.",
        extra={"issues": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    LOGGER.exception("Unhandled API error [request_id=%s]", request_id, exc_info=exc)
    return _error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        detail="Lỗi nội bộ. Vui lòng kiểm tra log với request ID tương ứng.",
    )


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    payload: dict[str, Any] = {
        "detail": detail,
        "error": {"code": code, "message": detail},
        "requestId": request_id,
    }
    if extra:
        payload.update(extra)
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(payload, status_code=status_code, headers=response_headers)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", normalized_request_id(None))
