import json
import logging
import os
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_context: ContextVar[str] = ContextVar("request_id", default="")
LOG_FIELDS = (
    "method",
    "route",
    "status_code",
    "duration_ms",
    "operation",
    "outcome",
    "provider",
    "event_id",
    "user_id",
    "ministry_id",
    "slot_id",
    "update_id",
    "job_id",
    "attempt",
    "notification_type",
    "count",
    "error_type",
    "error_code",
    "correlation_id",
    "provider_request_id",
)


class JsonLogFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        # Only static event names and explicitly allowed metadata are exported.
        # Exception messages, HTTP URLs, payloads and LogRecord arguments may contain secrets.
        event = (
            record.msg
            if isinstance(record.msg, str) and re.fullmatch(r"[a-z][a-z0-9_.]+", record.msg)
            else "external.log"
        )
        data: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "event": event,
        }
        request_id = request_id_context.get()
        if request_id:
            data["request_id"] = request_id
        for field in LOG_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, (str, int, float, bool)):
                data[field] = value
        if record.exc_info and record.exc_info[0]:
            data["error_type"] = record.exc_info[0].__name__
            data["stack"] = [
                {
                    "file": os.path.basename(frame.filename),
                    "function": frame.name,
                    "line": frame.lineno,
                }
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(data, ensure_ascii=False)


def configure_logging(service: str) -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(service))
    logging.basicConfig(level=level, handlers=[handler], force=True)
    for name in ("httpx", "httpcore", "sqlalchemy.engine", "uvicorn.access"):
        dependency = logging.getLogger(name)
        dependency.handlers.clear()
        dependency.propagate = False
        dependency.addHandler(logging.NullHandler())
    server = logging.getLogger("uvicorn.error")
    server.handlers.clear()
    server.propagate = True
