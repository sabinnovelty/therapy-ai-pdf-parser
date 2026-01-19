"""
Logger utility module for structured logging.

Currently configured for console/server logging, but designed to easily
migrate to CloudWatch Logs in the future.

Uses structlog for structured, JSON-formatted logs that work seamlessly
with CloudWatch Logs Insights.
"""
import logging
import sys
from typing import Optional

import structlog
from structlog.types import Processor


def configure_logger(
    log_level: str = "INFO",
    enable_json: bool = False,
    cloudwatch_mode: bool = False,
) -> None:
    """
    Configure the application logger with structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: If True, output logs in JSON format (for CloudWatch)
        cloudwatch_mode: If True, configure for CloudWatch Logs (JSON + timestamps)
    """
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure processors for structured logging
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add JSON renderer for CloudWatch compatibility
    if enable_json or cloudwatch_mode:
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.AsyncBoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured structlog logger instance
    """
    return structlog.get_logger(name)


# Initialize logger with default configuration (console mode)
# Can be overridden by calling configure_logger() with different settings
configure_logger(
    log_level="INFO",
    enable_json=False,
    cloudwatch_mode=False,
)

# Export a default logger instance
logger = get_logger(__name__)
