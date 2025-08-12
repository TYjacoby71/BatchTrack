import os
from typing import Any, Dict, Optional

# Import lazily to avoid hard dependency during environments without the SDK
try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - import-time guard
    genai = None  # type: ignore


class GeminiService:
    """Thin wrapper around Google Generative AI (Gemini) SDK.

    Uses environment variables when args are omitted:
    - GEMINI_API_KEY
    - GEMINI_MODEL (default: gemini-1.5-flash)
    - GEMINI_EMBEDDING_MODEL (default: text-embedding-004)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        safety_settings: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        self.embedding_model = embedding_model or os.environ.get(
            "GEMINI_EMBEDDING_MODEL", "text-embedding-004"
        )
        self.safety_settings = safety_settings
        self.generation_config = generation_config or {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
        }

        self._configured = False
        self._model = None

    def _ensure_configured(self) -> None:
        if self._configured:
            return
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Set env var GEMINI_API_KEY to use Gemini."
            )
        if genai is None:
            raise RuntimeError(
                "google-generativeai SDK is not installed. Add 'google-generativeai' to requirements.txt."
            )
        genai.configure(api_key=self.api_key)
        self._configured = True

    def _get_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            self._ensure_configured()
            self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        **overrides: Any,
    ) -> str:
        """Generate text for a simple prompt.

        Returns the model's text output (empty string if none).
        """
        self._ensure_configured()
        model = self._get_model()
        if system_instruction:
            model = genai.GenerativeModel(self.model_name, system_instruction=system_instruction)

        generation_config = dict(self.generation_config)
        generation_config.update(overrides or {})

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=self.safety_settings,
        )
        return getattr(response, "text", "") or ""

    def generate_text_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        **overrides: Any,
    ):
        """Streamed text generation (yields chunks)."""
        self._ensure_configured()
        model = self._get_model()
        if system_instruction:
            model = genai.GenerativeModel(self.model_name, system_instruction=system_instruction)

        generation_config = dict(self.generation_config)
        generation_config.update(overrides or {})

        stream = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=self.safety_settings,
            stream=True,
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text

    def embed(self, text: str) -> Any:
        """Return an embedding vector for the given text."""
        self._ensure_configured()
        result = genai.embed_content(model=self.embedding_model, content=text)
        # SDK may return dict or object depending on version
        if isinstance(result, dict):
            return result.get("embedding")
        # Fallbacks for older SDK shapes
        if hasattr(result, "embedding"):
            return result.embedding
        if hasattr(result, "embeddings") and getattr(result.embeddings, "values", None):
            return result.embeddings.values
        return result


# Convenience singleton (optional use)
_gemini_singleton: Optional[GeminiService] = None


def get_gemini() -> GeminiService:
    global _gemini_singleton
    if _gemini_singleton is None:
        _gemini_singleton = GeminiService()
    return _gemini_singleton