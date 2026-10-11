"""Application-owned JSON logging with bounded, redacted context."""

import json
import logging
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
SENSITIVE_KEY = re.compile(
    r"password|passwd|secret|token|authorization|cookie|api[_-]?key|database[_-]?url|connection",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.IGNORECASE)
ASSIGNMENT_PATTERN = re.compile(
    r"\b(password|pgpassword|token|secret|api[_-]?key|authorization|cookie)"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)


def exception_summary(exception: BaseException) -> dict[str, Any]:
    """Keep the origin location, never stack traces, messages, locals, or source."""
    frames = traceback.extract_tb(exception.__traceback__)
    summary: dict[str, Any] = {"type": type(exception).__name__}
    if frames:
        frame = frames[-1]
        summary["origin"] = {
            "file": Path(frame.filename).name,
            "line": frame.lineno,
            "function": frame.name,
        }
    return summary


class Redactor:
    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        self.secrets = sorted(secrets, key=len, reverse=True)

    def text(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        value = URL_PATTERN.sub("[REDACTED_URL]", value)
        value = BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        return ASSIGNMENT_PATTERN.sub(r"\1=[REDACTED]", value)

    def value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                self.text(str(key)): "[REDACTED]"
                if SENSITIVE_KEY.search(str(key))
                else self.value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.value(item) for item in value]
        if isinstance(value, str):
            return self.text(value)
        if value is None or isinstance(value, (int, float, bool)):
            return value
        return "[UNSUPPORTED]"


class JsonFormatter(logging.Formatter):
    def __init__(self, redactor: Redactor) -> None:
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.redactor.text(record.getMessage()),
            "request_id": request_id_context.get(),
        }
        context = getattr(record, "event_data", None)
        if context is not None:
            payload["context"] = self.redactor.value(context)
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = exception_summary(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)


class SafeStdoutHandler(logging.StreamHandler):
    """Follow replaced stdout streams; never dump raw records on sink failures."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        # logging's default handler prints raw exception messages and record arguments.
        try:
            sys.stderr.write("StockInsight logging sink unavailable\n")
        except (OSError, ValueError):
            pass  # A failed stderr cannot provide a second safe diagnostic channel.


def configure_logging(settings: Settings) -> Redactor:
    """Own only the stockinsight logger, without mutating third-party/root handlers."""
    redactor = Redactor(settings.secret_values())
    logger = logging.getLogger("stockinsight")
    handler = SafeStdoutHandler()
    handler.setFormatter(JsonFormatter(redactor))
    for existing in logger.handlers[:]:
        logger.removeHandler(existing)
        existing.close()
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
    return redactor
