"""CAPTCHA verification helpers for public checkout surfaces."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)


class CaptchaService:
    """Verify user CAPTCHA challenges with provider APIs."""

    _TURNSTILE_VERIFY_URL = (
        "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    )

    @classmethod
    def provider(cls) -> str:
        if not has_app_context():
            return "none"
        raw = current_app.config.get("CAPTCHA_PROVIDER", "none")
        return str(raw or "none").strip().lower()

    @classmethod
    def is_turnstile_enabled(cls) -> bool:
        if cls.provider() != "turnstile":
            return False
        return bool(cls.turnstile_site_key() and cls.turnstile_secret_key())

    @classmethod
    def turnstile_site_key(cls) -> str:
        if not has_app_context():
            return ""
        return str(current_app.config.get("CAPTCHA_TURNSTILE_SITE_KEY") or "").strip()

    @classmethod
    def turnstile_secret_key(cls) -> str:
        if not has_app_context():
            return ""
        return str(current_app.config.get("CAPTCHA_TURNSTILE_SECRET_KEY") or "").strip()

    @classmethod
    def verify_signup_token(
        cls,
        *,
        token: str | None,
        remote_ip: str | None,
    ) -> tuple[bool, str | None]:
        """Verify signup CAPTCHA token when Turnstile is enabled."""
        if not cls.is_turnstile_enabled():
            return True, None

        normalized_token = str(token or "").strip()
        if not normalized_token:
            return False, "Please complete the security check to continue."

        payload = {
            "secret": cls.turnstile_secret_key(),
            "response": normalized_token,
        }
        if remote_ip:
            payload["remoteip"] = str(remote_ip).strip()

        timeout_seconds = current_app.config.get("CAPTCHA_VERIFY_TIMEOUT_SECONDS", 5)
        try:
            timeout = max(1, int(timeout_seconds))
        except (TypeError, ValueError):
            timeout = 5

        request = Request(
            cls._TURNSTILE_VERIFY_URL,
            data=urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                response_payload: dict[str, Any] = json.loads(
                    response.read().decode("utf-8")
                )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.warning("Captcha verification request failed: %s", exc)
            return (
                False,
                "Security verification is temporarily unavailable. Please try again.",
            )

        if bool(response_payload.get("success")):
            return True, None

        logger.info(
            "Turnstile verification failed with codes: %s",
            response_payload.get("error-codes"),
        )
        return False, "Please complete the security check to continue."
