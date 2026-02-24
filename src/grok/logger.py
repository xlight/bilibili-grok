"""Structured logging for Bilibili Grok."""

import json
import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

import yaml


SENSITIVE_KEYS = {
    "sessdata",
    "bili_jct",
    "buvid3",
    "dedeuserid",
    "api_key",
    "api_key",
    "token",
    "secret",
    "password",
}


class SensitiveDataFilter(logging.Filter):
    """Filter out sensitive data from log records."""

    def __init__(self, sensitive_keys: Optional[set[str]] = None):
        super().__init__()
        self.sensitive_keys = sensitive_keys or SENSITIVE_KEYS

    def _mask_value(self, value: str) -> str:
        """Mask sensitive value."""
        if len(value) <= 4:
            return "****"
        return value[:2] + "****" + value[-2:]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from record."""
        if not hasattr(record, "msg"):
            return True

        msg = str(record.msg)

        for key in self.sensitive_keys:
            pattern = rf'({key})["\']?\s*[:=]\s*["\']?([^\'",}}]+)["\']?'
            msg = re.sub(
                pattern,
                rf'\1: "{self._mask_value(r"\2")}"',
                msg,
                flags=re.IGNORECASE,
            )

        record.msg = msg
        return True


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if self.include_extra:
            extra = {
                k: v
                for k, v in record.__dict__.items()
                if k
                not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "thread",
                    "threadName",
                    "message",
                    "asctime",
                )
            }
            if extra:
                log_data["extra"] = extra

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    format_: str = "text",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Logger:
    """Setup logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_: Log format (text or json)
        log_file: Path to log file (optional)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger
    """
    logger = logging.getLogger("grok")
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, level.upper()))
    handler.addFilter(SensitiveDataFilter())

    if format_.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.addFilter(SensitiveDataFilter())
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"grok.{name}")
