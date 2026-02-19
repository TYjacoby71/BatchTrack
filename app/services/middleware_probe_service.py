"""Unknown-endpoint probe policy for request middleware.

Synopsis:
Classifies suspicious unknown paths and applies bot-trap blocking for scanner probes.

Glossary:
- Unknown endpoint: Request path that does not resolve to a Flask endpoint.
- Scanner probe: High-signal path patterns used by opportunistic exploit bots.
"""

from __future__ import annotations

import logging

from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

from .public_bot_trap_service import PublicBotTrapService

logger = logging.getLogger(__name__)


class MiddlewareProbeService:
    """Centralized policy for unknown endpoint handling in middleware."""

    SUSPICIOUS_UNKNOWN_PATH_PREFIXES = (
        "/wp-",
        "/wordpress",
        "/xmlrpc.php",
        "/phpmyadmin",
        "/pma",
        "/adminer",
        "/cgi-bin",
        "/.git",
        "/.svn",
        "/.hg",
        "/.env",
        "/vendor/phpunit",
    )

    SUSPICIOUS_UNKNOWN_PATH_TOKENS = (
        "wp-content",
        "wp-includes",
        "wp-admin",
        ".env",
        "docker-compose",
        "nginx.conf",
        "httpd.conf",
        "selfsigned",
        "cert.pem",
        "ssl.key",
        "secret",
        "setup-config.php",
        "app_dev.php",
        "config_dev.php",
        "phpmyadmin",
        "adminer.php",
    )

    SUSPICIOUS_UNKNOWN_PATH_SUFFIXES = (
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".cgi",
        ".pl",
        ".env",
        ".ini",
        ".conf",
        ".yml",
        ".yaml",
        ".sql",
        ".bak",
        ".pem",
        ".key",
        ".crt",
        ".sh",
    )

    @classmethod
    def derive_unknown_endpoint_status(cls, request) -> int | None:
        """Return status code for an unmatched route, preserving canonical redirects."""
        routing_error = getattr(request, "routing_exception", None)
        if routing_error is None:
            return 404
        if isinstance(routing_error, RequestRedirect):
            # Allow Flask/Werkzeug to handle canonical slash or host redirects.
            return None
        if isinstance(routing_error, MethodNotAllowed):
            return 405
        if isinstance(routing_error, NotFound):
            return 404
        code = getattr(routing_error, "code", None)
        if isinstance(code, int) and 400 <= code < 600:
            return code
        return 404

    @classmethod
    def is_suspicious_unknown_path(cls, path: str) -> bool:
        """Classify high-signal scanner probe paths."""
        normalized_path = (path or "").strip().lower()
        if not normalized_path or normalized_path == "/":
            return False
        if any(
            normalized_path.startswith(prefix)
            for prefix in cls.SUSPICIOUS_UNKNOWN_PATH_PREFIXES
        ):
            return True
        if any(
            token in normalized_path for token in cls.SUSPICIOUS_UNKNOWN_PATH_TOKENS
        ):
            return True
        last_segment = normalized_path.rsplit("/", 1)[-1]
        if any(
            last_segment.endswith(suffix)
            for suffix in cls.SUSPICIOUS_UNKNOWN_PATH_SUFFIXES
        ):
            return True
        return False

    @classmethod
    def maybe_block_suspicious_unknown_probe(
        cls, *, request, path: str, status_code: int
    ) -> None:
        """Persist a bot-trap block when an unknown path looks like a scanner probe."""
        if not cls.is_suspicious_unknown_path(path):
            return
        try:
            request_ip = PublicBotTrapService.resolve_request_ip(request)
            if not request_ip or PublicBotTrapService.is_blocked(ip=request_ip):
                return
            PublicBotTrapService.record_hit(
                request=request,
                source="middleware_unknown_endpoint",
                reason="suspicious_unknown_path",
                extra={"status_code": status_code, "path": path},
                block=True,
            )
            logger.warning(
                "Auto-blocked suspicious unknown-path probe: path=%s ip=%s status=%s",
                path,
                request_ip,
                status_code,
            )
        except Exception as exc:
            logger.warning(
                "Unable to auto-block suspicious unknown path %s: %s", path, exc
            )
