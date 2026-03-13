"""Cloudflare Turnstile verification helpers for public forms."""

from __future__ import annotations

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class TurnstileService:
    """Validate Cloudflare Turnstile challenge responses."""

    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    @staticmethod
    def site_key() -> str:
        return str(current_app.config.get("TURNSTILE_SITE_KEY") or "").strip()

    @staticmethod
    def secret_key() -> str:
        return str(current_app.config.get("TURNSTILE_SECRET_KEY") or "").strip()

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(cls.site_key() and cls.secret_key())

    @classmethod
    def verify_response(cls, response_token: str | None, remote_ip: str | None) -> bool:
        """Return True when Turnstile verification succeeds.

        If Turnstile is not configured, verification is treated as optional and passes.
        """
        if not cls.is_enabled():
            return True

        token = str(response_token or "").strip()
        if not token:
            return False

        payload: dict[str, str] = {
            "secret": cls.secret_key(),
            "response": token,
        }
        client_ip = str(remote_ip or "").strip()
        if client_ip:
            payload["remoteip"] = client_ip

        try:
            response = requests.post(cls.VERIFY_URL, data=payload, timeout=5)
            response.raise_for_status()
            result = response.json() or {}
        except Exception as exc:
            logger.warning("Turnstile verification request failed: %s", exc)
            return False

        success = bool(result.get("success"))
        if not success:
            logger.info(
                "Turnstile verification rejected: %s",
                ",".join(result.get("error-codes") or []),
            )
        return success
