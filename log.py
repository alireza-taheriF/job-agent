"""
Logging shim: use structlog when available, fall back to stdlib.
Provides structlog-style call signatures (positional message + keyword context)
so callers work unchanged regardless of which backend is active.
"""

try:
    import structlog as _structlog

    def configure():
        _structlog.configure(
            processors=[
                _structlog.stdlib.add_log_level,
                _structlog.stdlib.PositionalArgumentsFormatter(),
                _structlog.processors.TimeStamper(fmt="iso"),
                _structlog.dev.ConsoleRenderer(),
            ]
        )

    def get_logger(name: str = ""):
        return _structlog.get_logger(name) if name else _structlog.get_logger()

except ImportError:
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    )

    class _StdlibLogger:
        """Thin wrapper that accepts structlog-style keyword context."""

        def __init__(self, name: str):
            self._inner = _logging.getLogger(name)

        def _fmt(self, msg, kw):
            if kw:
                extra = " ".join(f"{k}={v!r}" for k, v in kw.items())
                return f"{msg} {extra}"
            return str(msg)

        def debug(self, msg, **kw): self._inner.debug(self._fmt(msg, kw))
        def info(self, msg, **kw): self._inner.info(self._fmt(msg, kw))
        def warning(self, msg, **kw): self._inner.warning(self._fmt(msg, kw))
        def warn(self, msg, **kw): self._inner.warning(self._fmt(msg, kw))
        def error(self, msg, **kw): self._inner.error(self._fmt(msg, kw))
        def exception(self, msg, **kw): self._inner.exception(self._fmt(msg, kw))
        def critical(self, msg, **kw): self._inner.critical(self._fmt(msg, kw))

    def configure():  # noqa: F811
        pass

    def get_logger(name: str = ""):  # noqa: F811
        return _StdlibLogger(name or "job-agent")
