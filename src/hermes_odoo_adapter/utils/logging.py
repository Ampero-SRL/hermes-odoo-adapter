"""
Structured logging utilities for HERMES Odoo Adapter
"""
import sys
import logging
from typing import Any, Dict, Optional
from contextvars import ContextVar

import structlog
from structlog.types import FilteringBoundLogger

from ..settings import settings

# Context variables for correlation tracking
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
project_id_var: ContextVar[Optional[str]] = ContextVar("project_id", default=None)


def add_correlation_context(
    logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add correlation context to log events"""
    correlation_id = correlation_id_var.get()
    project_id = project_id_var.get()
    
    if correlation_id:
        event_dict["correlationId"] = correlation_id
    if project_id:
        event_dict["projectId"] = project_id
    
    return event_dict


def setup_logging() -> None:
    """Setup structured logging with JSON output"""
    
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper())
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add correlation context
            add_correlation_context,
            # Add log level
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="ISO", utc=True),
            # Add stack info for errors
            structlog.processors.StackInfoRenderer(),
            # Format exceptions
            structlog.processors.format_exc_info,
            # Convert to dict for JSON serialization
            structlog.processors.JSONRenderer() if not settings.testing 
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s" if not settings.testing else "%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> FilteringBoundLogger:
    """Get a structured logger instance"""
    logger_name = name or __name__
    return structlog.get_logger(logger_name)


class LoggingContext:
    """Context manager for setting correlation context"""
    
    def __init__(
        self, 
        correlation_id: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        self.correlation_id = correlation_id
        self.project_id = project_id
        self._correlation_token = None
        self._project_token = None
    
    def __enter__(self) -> "LoggingContext":
        if self.correlation_id:
            self._correlation_token = correlation_id_var.set(self.correlation_id)
        if self.project_id:
            self._project_token = project_id_var.set(self.project_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._correlation_token:
            correlation_id_var.reset(self._correlation_token)
        if self._project_token:
            project_id_var.reset(self._project_token)


def with_context(
    correlation_id: Optional[str] = None,
    project_id: Optional[str] = None
):
    """Decorator to add logging context to functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with LoggingContext(correlation_id=correlation_id, project_id=project_id):
                return func(*args, **kwargs)
        return wrapper
    return decorator