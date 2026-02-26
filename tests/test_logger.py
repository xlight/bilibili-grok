"""Tests for logger module."""

import json
import logging
from io import StringIO
from pathlib import Path

import pytest

from grok.logger import JsonFormatter, SensitiveDataFilter, get_logger, setup_logging


class TestSensitiveDataFilter:
    def test_filter_sessdata(self):
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='sessdata: "secret_value_12345"',
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "secret_value_12345" not in record.msg
        assert "****" in record.msg

    def test_filter_bili_jct(self):
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='bili_jct: "my_secret_token"',
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "my_secret_token" not in record.msg
        assert "****" in record.msg

    def test_filter_api_key(self):
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='api_key: "sk-test-key-12345"',
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "sk-test-key-12345" not in record.msg
        assert "****" in record.msg

    def test_filter_short_value(self):
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='sessdata: "abc"',
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "abc" not in record.msg
        assert "****" in record.msg

    def test_filter_preserves_non_sensitive(self):
        filter_obj = SensitiveDataFilter()
        original_msg = "Normal log message without sensitive data"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=original_msg,
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.msg == original_msg

    def test_custom_sensitive_keys(self):
        filter_obj = SensitiveDataFilter(sensitive_keys={"custom_key"})
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='custom_key: "secret"',
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "secret" not in record.msg

    def test_filter_no_msg_attribute(self):
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        delattr(record, "msg")

        result = filter_obj.filter(record)

        assert result is True


class TestJsonFormatter:
    def test_format_basic_fields(self):
        formatter = JsonFormatter(include_extra=False)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        assert data["function"] == "test_func"
        assert data["line"] == 42
        assert "timestamp" in data

    def test_format_with_exception(self):
        formatter = JsonFormatter(include_extra=False)
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.module = "test"
        record.funcName = "test_func"

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]

    def test_format_with_extra(self):
        formatter = JsonFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"
        record.custom_field = "custom_value"

        output = formatter.format(record)
        data = json.loads(output)

        assert "extra" in data
        assert data["extra"]["custom_field"] == "custom_value"

    def test_format_no_extra_when_disabled(self):
        formatter = JsonFormatter(include_extra=False)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"
        record.custom_field = "custom_value"

        output = formatter.format(record)
        data = json.loads(output)

        assert "extra" not in data


class TestSetupLogging:
    def test_setup_logging_text_format(self, tmp_path):
        log_file = tmp_path / "test.log"

        logger = setup_logging(
            level="INFO",
            format_="text",
            log_file=str(log_file),
        )

        assert logger.name == "grok"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 2

    def test_setup_logging_json_format(self, tmp_path):
        log_file = tmp_path / "test.log"

        logger = setup_logging(
            level="DEBUG",
            format_="json",
            log_file=str(log_file),
        )

        assert logger.level == logging.DEBUG
        assert any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers)

    def test_setup_logging_no_file(self):
        logger = setup_logging(level="WARNING", format_="text", log_file=None)

        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 1

    def test_setup_logging_creates_log_directory(self, tmp_path):
        log_file = tmp_path / "subdir" / "test.log"

        logger = setup_logging(
            level="INFO",
            format_="text",
            log_file=str(log_file),
        )

        assert log_file.parent.exists()

    def test_setup_logging_adds_sensitive_filter(self, tmp_path):
        log_file = tmp_path / "test.log"

        logger = setup_logging(
            level="INFO",
            format_="text",
            log_file=str(log_file),
        )

        for handler in logger.handlers:
            filters = [f for f in handler.filters if isinstance(f, SensitiveDataFilter)]
            assert len(filters) > 0


class TestGetLogger:
    def test_get_logger_returns_logger(self):
        logger = get_logger("test")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "grok.test"

    def test_get_logger_different_names(self):
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "grok.module1"
        assert logger2.name == "grok.module2"
