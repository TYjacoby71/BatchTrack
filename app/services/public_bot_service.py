from __future__ import annotations

from typing import Mapping, Optional

from flask import current_app

from app.services.ai import GoogleAIClient

PUBLIC_HELP_CONTEXT = """
BatchTrack (batchtrack.com) overview:
- Production OS for makers of soap, candles, cosmetics, food, and other batch goods.
- Core modules: Inventory, Recipes, Production Planning, Batches, Products/SKUs, Exports, Reporting, and Developer/Automation tooling.
- Onboarding path: add inventory or a recipe first, invite teammates, then plan your first batch from the dashboard ribbons.
- Inventory: unified drawer for ingredients, containers, packaging, consumables with FIFO lots and adjustments (restock, spoil, recount, manual tweaks).
- Recipes: store yield, portions, instructions/SOPs, container shortlists, ingredient + consumable lines, labels/INCI exports.
- Production Planning: build immutable plan snapshots, auto-select containers by yield, enforce stock checks, launch batches with timers/extras/notes.
- Products & SKUs: link finished batches to sellable goods, track reservations, map Shopify/Square IDs for integrations.
- Reports & Exports: costing (planned vs actual), inventory valuation, compliance labels, INCI sheets, baker/lotion/candle exports, audit-friendly history.
- Public tools: /tools calculators mirror recipe exports so prospects can experiment before signing up.
- Support: help center topics include getting started, inventory workflows, planning, costing, products/SKUs, and labels/exports.
"""


class PublicBotServiceError(RuntimeError):
    pass


class PublicBotService:
    """Lightweight helper that answers public questions using curated help context."""

    def __init__(self) -> None:
        cfg = current_app.config
        if not cfg.get("GOOGLE_AI_API_KEY"):
            raise PublicBotServiceError("GOOGLE_AI_API_KEY is not configured.")
        self.client = GoogleAIClient.from_app()
        self.model_name = cfg.get("GOOGLE_AI_PUBLICBOT_MODEL") or cfg.get(
            "GOOGLE_AI_DEFAULT_MODEL"
        )

    def answer(
        self, prompt: str, *, tone: Optional[str] = None
    ) -> Mapping[str, object]:
        if not prompt:
            raise PublicBotServiceError("Question is required.")

        tone_hint = tone or "friendly and concise"
        composed_prompt = (
            f"{PUBLIC_HELP_CONTEXT.strip()}\n\n"
            f"Visitor question: {prompt.strip()}\n"
            f"Respond in a {tone_hint} tone. Cite the relevant module names when helpful."
        )

        result = self.client.generate_content(
            contents=[{"role": "user", "parts": [{"text": composed_prompt}]}],
            model=self.model_name,
            system_instruction=(
                "You are the public help bot for BatchTrack. Provide precise, marketing-safe answers "
                "based only on the supplied context. When unsure, recommend contacting support."
            ),
            generation_config={"temperature": 0.5, "max_output_tokens": 768},
        )

        return {
            "text": result.text,
            "usage": result.usage_metadata or {},
            "model": self.model_name,
        }
