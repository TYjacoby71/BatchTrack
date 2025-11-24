from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from flask import current_app, g

__all__ = ["PerformanceMonitor", "profile_route"]

logger = logging.getLogger(__name__)
TFunc = TypeVar("TFunc", bound=Callable[..., Any])


class PerformanceMonitor:
    """Lightweight helpers for timing queries and request handlers."""

    DEFAULT_QUERY_THRESHOLD = 0.1
    DEFAULT_ROUTE_THRESHOLD = 1.0

    @staticmethod
    def init_request_metrics() -> None:
        """Ensure request-scoped counters exist on `g`."""
        if not hasattr(g, "perf_metrics"):
            g.perf_metrics = {"query_count": 0, "query_time": 0.0}

    @staticmethod
    def record_query(duration: float) -> None:
        """Increment counters for an observed database query."""
        PerformanceMonitor.init_request_metrics()
        g.perf_metrics["query_count"] += 1
        g.perf_metrics["query_time"] += max(duration, 0.0)

    @staticmethod
    def log_slow_calls(threshold: float = DEFAULT_QUERY_THRESHOLD) -> Callable[[TFunc], TFunc]:
        """
        Decorator that logs whenever the wrapped callable exceeds *threshold* seconds.
        Intended for instrumenting ORM or service-layer methods without external tooling.
        """

        def decorator(func: TFunc) -> TFunc:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.perf_counter() - start
                    if duration >= threshold:
                        PerformanceMonitor._emit_warning(
                            f"Slow call: {func.__qualname__}", duration
                        )

            return wrapper  # type: ignore[return-value]

        return decorator

    @staticmethod
    def _emit_warning(message: str, duration: float) -> None:
        log_target = current_app.logger if current_app else logger
        log_target.warning("%s (%.3fs)", message, duration)


def profile_route(func: TFunc, *, threshold: float = PerformanceMonitor.DEFAULT_ROUTE_THRESHOLD) -> TFunc:
    """Decorator for view functions to log requests exceeding *threshold* seconds."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        response = func(*args, **kwargs)
        duration = time.perf_counter() - start
        if duration >= threshold:
            PerformanceMonitor._emit_warning(
                f"Slow route: {func.__name__}", duration
            )
        return response

    return wrapper  # type: ignore[return-value]
