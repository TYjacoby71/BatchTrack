"""AI worker responsible for calling the LLM and validating output."""
from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DEFAULT_INGREDIENT_CATEGORY_TAGS, DEFAULT_PHYSICAL_FORMS, Settings
from .schema import IngredientPayload

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    payload: IngredientPayload
    source: str  # e.g., "llm" or "stub"


class AIWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Optional[OpenAI] = None
        if not settings.dry_run and os.getenv("OPENAI_API_KEY"):
            self._client = OpenAI()
        else:
            logger.warning(
                "Running AI worker in dry-run mode (set OPENAI_API_KEY and unset DATA_BUILDER_DRY_RUN to enable live calls)."
            )

    def build_prompt(self, term: str) -> str:
        physical_forms = ", ".join(DEFAULT_PHYSICAL_FORMS)
        categories = ", ".join(DEFAULT_INGREDIENT_CATEGORY_TAGS)
        return f"""
You are an expert ingredient data extraction agent for a formulation SaaS.
Gather all available structured information about the ingredient named "{term}".
Return data for the abstract ingredient plus every common physical form/item.
The response MUST be valid JSON with this exact envelope:
{{
  "ingredient": {{
    "common_name": "...",
    "inci_name": "...",
    "cas_number": "...",
    "description": "...",
    "is_active_ingredient": true,
    "safety_notes": "...",
    "taxonomies": {{
      "ingredient_category_tags": ["tag from: {categories}"],
      "function_tags": ["..."],
      "application_tags": ["..."]
    }}
  }},
  "items": [
    {{
      "item_name": "Ingredient, Physical Form",
      "physical_form": "one of: {physical_forms}",
      "density_g_ml": 0.85,
      "shelf_life_days": 365,
      "ph_value": "4.5-6.0",
      "attributes": {{
        "solubility": "Water Soluble",
        "melting_point_c": 210
      }}
    }}
  ]
}}
If reliable data cannot be found, return {{"error": "Insufficient data for term: {term}"}}.
"""

    def generate(self, term: str) -> WorkerResult:
        if self._client is None:
            payload = self._fabricate_payload(term)
            return WorkerResult(payload=payload, source="stub")

        raw_json = self._call_llm(term)
        payload = IngredientPayload.model_validate_json(raw_json)
        return WorkerResult(payload=payload, source="llm")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _call_llm(self, term: str) -> str:
        response = self._client.responses.create(
            model=self.settings.llm_model,
            temperature=self.settings.temperature,
            response_format={"type": "json_object"},
            input=self.build_prompt(term),
        )
        try:
            message = response.output[0].content[0].text
        except (AttributeError, IndexError, KeyError) as exc:
            raise RuntimeError("Unexpected response payload from LLM") from exc
        return message

    def _fabricate_payload(self, term: str) -> IngredientPayload:
        random.seed(term)
        category = random.choice(DEFAULT_INGREDIENT_CATEGORY_TAGS)
        physical_form = random.choice(DEFAULT_PHYSICAL_FORMS)
        payload = {
            "ingredient": {
                "common_name": term,
                "inci_name": term,
                "cas_number": "000-00-0",
                "description": f"Synthetic placeholder data for {term}.",
                "is_active_ingredient": random.choice([True, False]),
                "safety_notes": "Not evaluated in dry-run mode.",
                "taxonomies": {
                    "ingredient_category_tags": [category],
                    "function_tags": ["Placeholder Function"],
                    "application_tags": ["Skin Care > Prototyping"],
                },
            },
            "items": [
                {
                    "item_name": f"{term}, {physical_form}",
                    "physical_form": physical_form,
                    "density_g_ml": round(random.uniform(0.2, 1.5), 2),
                    "shelf_life_days": random.choice([365, 540, 720, 1095]),
                    "ph_value": "5.0-7.0",
                    "attributes": {"source": "dry_run"},
                }
            ],
        }
        return IngredientPayload.model_validate(payload)


def parse_payload(raw: str) -> IngredientPayload:
    data = json.loads(raw)
    if "error" in data:
        raise ValueError(data["error"])
    return IngredientPayload.model_validate(data)


__all__ = ["AIWorker", "WorkerResult", "parse_payload"]
