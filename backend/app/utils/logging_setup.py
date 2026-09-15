"""
Structured logging configuration.

Kept intentionally simple for Phase 1: JSON-ish key=value console output.
No API keys, tokens, or raw source code should ever be passed into a log
call anywhere in this codebase -- see SECURITY notes in the README.
"""
import logging
import sys

_CONFIGURED = False


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record, '%Y-%m-%dT%H:%M:%S')} {record.levelname:<8} {record.name}: {record.getMessage()}"
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "asctime", "taskName",
            )
        }
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    _CONFIGURED = True
