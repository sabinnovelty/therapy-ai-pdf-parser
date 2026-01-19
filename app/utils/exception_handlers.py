"""
Exception handlers for FastAPI application.

Centralized exception handling with structured logging.
"""
import json
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Custom exception handler for request validation errors.

    Logs detailed validation error information with structured logging
    and returns a 422 response with error details.

    Args:
        request: The FastAPI request object
        exc: The RequestValidationError exception

    Returns:
        JSONResponse with validation error details
    """
    # Get request body if available
    body: Any = None
    if hasattr(exc, "body") and exc.body:
        try:
            body = (
                json.loads(exc.body.decode("utf-8"))
                if isinstance(exc.body, bytes)
                else exc.body
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = str(exc.body)[:500]  # Truncate if not valid JSON

    # Log validation errors with structured logging
    await logger.error(
        "Request validation failed",
        path=request.url.path,
        method=request.method,
        query_params=dict(request.query_params),
        validation_errors=exc.errors(),
        request_body=body,
    )

    # Log each validation error individually for better readability
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
        await logger.error(
            "Validation error detail",
            field=field_path,
            message=error.get("msg", ""),
            error_type=error.get("type", ""),
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": body,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    General exception handler for unhandled exceptions.

    Logs the exception with full context and returns a 500 response.

    Args:
        request: The FastAPI request object
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    await logger.error(
        "Unhandled exception occurred",
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred",
            "error_type": type(exc).__name__,
        },
    )
