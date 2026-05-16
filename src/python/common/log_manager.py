# Copyright 2017, Inderpreet Singh, All rights reserved.
# Enhanced logging system - 2025

"""
Centralized logging manager for RapidCopy.

This module provides:
- Centralized logger configuration
- Configurable log levels from config file
- Multiple output formats (standard, JSON)
- Consistent logger naming conventions
- Utility functions for creating child loggers
"""

import logging
import sys
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from .constants import Constants


class LogLevel:
    """Valid log level names and their mapping to logging constants."""

    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    @classmethod
    def from_string(cls, level_str: str) -> int:
        """
        Convert a string log level to logging constant.

        Args:
            level_str: Log level name (case-insensitive)

        Returns:
            logging level constant

        Raises:
            ValueError: If the level string is not recognized
        """
        level_upper = level_str.upper().strip()
        if level_upper not in cls.LEVELS:
            valid_levels = ", ".join(cls.LEVELS.keys())
            raise ValueError(f"Invalid log level '{level_str}'. Valid levels: {valid_levels}")
        return cls.LEVELS[level_upper]

    @classmethod
    def to_string(cls, level: int) -> str:
        """Convert a logging constant to string."""
        for name, value in cls.LEVELS.items():
            if value == level:
                return name
        return "UNKNOWN"


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Produces JSON output suitable for log aggregation tools like ELK, Splunk, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": {
                "name": record.processName,
                "id": record.process,
            },
            "thread": {
                "name": record.threadName,
                "id": record.thread,
            },
            "source": {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            },
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


class StandardFormatter(logging.Formatter):
    """
    Enhanced standard formatter with consistent output.

    Format: TIMESTAMP - LEVEL - LOGGER (PROCESS/THREAD) - MESSAGE
    """

    DEFAULT_FORMAT = "%(asctime)s - %(levelname)s - %(name)s (%(processName)s/%(threadName)s) - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, include_thread_info: bool = True):
        if include_thread_info:
            fmt = self.DEFAULT_FORMAT
        else:
            fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        super().__init__(fmt=fmt, datefmt=self.DEFAULT_DATE_FORMAT)


class LogManager:
    """
    Centralized logging manager for RapidCopy.

    Provides factory methods for creating loggers with consistent configuration.
    """

    # Default logger instances (set during initialization)
    _main_logger: logging.Logger | None = None
    _web_access_logger: logging.Logger | None = None

    # Configuration
    _log_dir: str | None = None
    _log_level: int = logging.INFO
    _use_json: bool = False

    @classmethod
    def initialize(
        cls,
        log_dir: str | None = None,
        log_level: str | int = logging.INFO,
        use_json: bool = False,
        debug: bool = False,
    ) -> None:
        """
        Initialize the logging system.

        Args:
            log_dir: Directory to write log files. If None, logs to stdout.
            log_level: Log level (string name or logging constant). Ignored if debug=True.
            use_json: If True, use JSON format for log output.
            debug: If True, force DEBUG level (overrides log_level).
        """
        # Determine effective log level
        if debug:
            cls._log_level = logging.DEBUG
        elif isinstance(log_level, str):
            cls._log_level = LogLevel.from_string(log_level)
        else:
            cls._log_level = log_level

        cls._log_dir = log_dir
        cls._use_json = use_json

        # Create main loggers
        cls._main_logger = cls.create_logger(Constants.SERVICE_NAME)
        cls._web_access_logger = cls.create_logger(Constants.WEB_ACCESS_LOG_NAME)

        # Log initialization
        cls._main_logger.info(
            f"Logging initialized: level={LogLevel.to_string(cls._log_level)}, "
            f"output={'file' if log_dir else 'stdout'}, "
            f"format={'json' if use_json else 'standard'}"
        )

    @classmethod
    def create_logger(
        cls,
        name: str,
        level: int | None = None,
        log_dir: str | None = None,
    ) -> logging.Logger:
        """
        Create a new logger with the standard RapidCopy configuration.

        Args:
            name: Logger name (will be prefixed with service name if not already)
            level: Log level. If None, uses the global log level.
            log_dir: Override log directory. If None, uses the global setting.

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)

        # Remove any existing handlers
        cls._clear_handlers(logger)

        # Set level
        effective_level = level if level is not None else cls._log_level
        logger.setLevel(effective_level)

        # Create handler
        effective_log_dir = log_dir if log_dir is not None else cls._log_dir
        handler = cls._create_handler(name, effective_log_dir)

        # Create formatter
        formatter = cls._create_formatter()
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return logger

    @classmethod
    def get_main_logger(cls) -> logging.Logger:
        """Get the main application logger."""
        if cls._main_logger is None:
            raise RuntimeError("LogManager not initialized. Call LogManager.initialize() first.")
        return cls._main_logger

    @classmethod
    def get_web_access_logger(cls) -> logging.Logger:
        """Get the web access logger."""
        if cls._web_access_logger is None:
            raise RuntimeError("LogManager not initialized. Call LogManager.initialize() first.")
        return cls._web_access_logger

    @classmethod
    def create_child_logger(cls, parent: logging.Logger, child_name: str) -> logging.Logger:
        """
        Create a child logger from a parent logger.

        Uses hierarchical naming: parent.child_name

        Args:
            parent: Parent logger
            child_name: Name for the child logger

        Returns:
            Child logger instance
        """
        return parent.getChild(child_name)

    @classmethod
    def set_log_level(cls, level: str | int) -> None:
        """
        Change the log level at runtime.

        Args:
            level: New log level (string name or logging constant)
        """
        if isinstance(level, str):
            cls._log_level = LogLevel.from_string(level)
        else:
            cls._log_level = level

        # Update existing loggers
        if cls._main_logger:
            cls._main_logger.setLevel(cls._log_level)
            cls._main_logger.info(f"Log level changed to {LogLevel.to_string(cls._log_level)}")

        if cls._web_access_logger:
            cls._web_access_logger.setLevel(cls._log_level)

    @classmethod
    def get_log_level(cls) -> int:
        """Get the current log level."""
        return cls._log_level

    @classmethod
    def _clear_handlers(cls, logger: logging.Logger) -> None:
        """Remove all handlers from a logger."""
        handlers = logger.handlers[:]
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)

    @classmethod
    def _create_handler(cls, name: str, log_dir: str | None) -> logging.Handler:
        """Create the appropriate handler based on configuration."""
        if log_dir is not None:
            return RotatingFileHandler(
                f"{log_dir}/{name}.log",
                maxBytes=Constants.MAX_LOG_SIZE_IN_BYTES,
                backupCount=Constants.LOG_BACKUP_COUNT,
            )
        else:
            return logging.StreamHandler(sys.stdout)

    @classmethod
    def _create_formatter(cls) -> logging.Formatter:
        """Create the appropriate formatter based on configuration."""
        if cls._use_json:
            return JsonFormatter()
        else:
            return StandardFormatter(include_thread_info=True)


# Convenience functions for module-level usage
def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.

    This is a convenience function that wraps LogManager.create_logger().
    If LogManager is not initialized, returns a basic logger.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    try:
        return LogManager.create_logger(name)
    except Exception:
        # Fallback to basic logger if LogManager not initialized
        return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context: Any,
) -> None:
    """
    Log a message with additional context data.

    When using JSON formatting, context data is included in the log output.

    Args:
        logger: Logger to use
        level: Log level
        message: Log message
        **context: Additional context data to include
    """
    extra = {"extra_data": context} if context else {}
    logger.log(level, message, extra=extra)
