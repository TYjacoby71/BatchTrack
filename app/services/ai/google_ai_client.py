"""Thin wrapper around google-generativeai so the rest of the app has a single entrypoint."""

from __future__ import annotations
import logging

import threading
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
)

import google.generativeai as genai
from flask import current_app

logger = logging.getLogger(__name__)



class GoogleAIClientError(RuntimeError):
    """Raised when the Google AI client cannot fulfil a request."""


@dataclass(slots=True)
class GoogleAIResult:
    """Normalized subset of the Gemini response we care about."""

    text: str
    raw: Any
    finish_reason: str | None = None
    usage_metadata: Mapping[str, Any] | None = None
    tool_calls: Sequence[Mapping[str, Any]] | None = None


class GoogleAIClient:
    """Centralized Gemini client configured from Flask settings."""

    _configure_lock = threading.Lock()
    _configured = False

    def __init__(
        self,
        api_key: str,
        *,
        default_model: str = "gemini-1.5-flash",
        request_timeout: int = 45,
    ) -> None:
        if not api_key:
            raise GoogleAIClientError("GOOGLE_AI_API_KEY is not configured.")

        self._api_key = api_key
        self._default_model = default_model or "gemini-1.5-flash"
        self._request_timeout = request_timeout
        self._models: Dict[str, genai.GenerativeModel] = {}
        self._ensure_global_configuration()

    @classmethod
    def from_app(cls) -> "GoogleAIClient":
        """Factory using the current Flask config."""
        cfg = current_app.config
        return cls(
            api_key=cfg.get("GOOGLE_AI_API_KEY"),
            default_model=cfg.get("GOOGLE_AI_DEFAULT_MODEL") or "gemini-1.5-flash",
            request_timeout=int(cfg.get("BATCHBOT_REQUEST_TIMEOUT_SECONDS", 45)),
        )

    def _ensure_global_configuration(self) -> None:
        if not self.__class__._configured:
            with self.__class__._configure_lock:
                if not self.__class__._configured:
                    genai.configure(api_key=self._api_key)
                    self.__class__._configured = True

    def _get_model(self, model_name: Optional[str] = None) -> genai.GenerativeModel:
        name = model_name or self._default_model
        if not name:
            raise GoogleAIClientError("No Gemini model name provided.")

        model = self._models.get(name)
        if model is None:
            model = genai.GenerativeModel(name=name)
            self._models[name] = model
        return model

    def generate_content(
        self,
        *,
        contents: Sequence[Mapping[str, Any]],
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[Sequence[Mapping[str, Any]]] = None,
        tool_config: Optional[Mapping[str, Any]] = None,
        safety_settings: Optional[Sequence[Mapping[str, Any]]] = None,
        generation_config: Optional[Mapping[str, Any]] = None,
        stream: bool = False,
    ) -> GoogleAIResult:
        """Call Gemini and normalize the response."""
        if not contents:
            raise GoogleAIClientError(
                "Gemini requests require at least one content block."
            )

        payload: MutableMapping[str, Any] = {
            "contents": list(contents),
            "system_instruction": system_instruction,
            "tools": list(tools) if tools else None,
            "tool_config": tool_config,
            "safety_settings": safety_settings,
            "generation_config": generation_config,
        }

        # Remove keys whose values are None to keep requests tidy.
        payload = {key: value for key, value in payload.items() if value is not None}

        model_instance = self._get_model(model)
        try:
            response = model_instance.generate_content(
                **payload,
                request_options={"timeout": self._request_timeout},
                stream=stream,
            )
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("Suppressed exception fallback at app/services/ai/google_ai_client.py:124", exc_info=True)
            raise GoogleAIClientError(f"Gemini request failed: {exc}") from exc

        # Streamed responses return a generator; consolidate into one object.
        if stream:
            response = _collect_stream(response)

        text = _first_text(response)
        finish_reason = (
            getattr(response, "candidates", [{}])[0].get("finish_reason")
            if hasattr(response, "candidates")
            else None
        )
        usage = getattr(response, "usage_metadata", None)
        tool_calls = _extract_tool_calls(response)

        return GoogleAIResult(
            text=text,
            raw=response,
            finish_reason=finish_reason,
            usage_metadata=usage,
            tool_calls=tool_calls,
        )


def _collect_stream(stream_response: Iterable[Any]) -> Any:
    """Combine streaming chunks into a single response-like object."""
    final = None
    chunks: List[Any] = []
    for chunk in stream_response:
        chunks.append(chunk)
        final = chunk
    return final or chunks[-1]


def _first_text(response: Any) -> str:
    """Extract the first text block from a Gemini response."""
    if not response:
        return ""

    try:
        parts = response.candidates[0].content.parts  # type: ignore[attr-defined]
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                return text
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/ai/google_ai_client.py:170", exc_info=True)
        pass

    # Fallback to string conversion.
    return str(response or "")


def _extract_tool_calls(response: Any) -> Sequence[Mapping[str, Any]] | None:
    """Return tool call payloads (function calls) if present."""
    try:
        candidates = getattr(response, "candidates", [])
        if not candidates:
            return None
        content = candidates[0].content
        collected: List[Mapping[str, Any]] = []
        for part in getattr(content, "parts", []):
            if getattr(part, "function_call", None):
                collected.append(part.function_call)
            elif getattr(part, "executable_code", None):
                collected.append(part.executable_code)
        return collected or None
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/ai/google_ai_client.py:191", exc_info=True)
        return None
