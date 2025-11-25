from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence

from flask import current_app
from sqlalchemy import asc, desc

from app.models import Batch, InventoryItem, Recipe
from app.services.ai import GoogleAIClient
from app.services.batchbot_usage_service import BatchBotUsageService, BatchBotUsageSnapshot
from app.services.inventory_adjustment import process_inventory_adjustment
from app.utils.timezone_utils import TimezoneUtils


class BatchBotServiceError(RuntimeError):
    """Base exception for BatchBot orchestration errors."""


@dataclass(slots=True)
class BatchBotResponse:
    text: str
    tool_results: Sequence[Mapping[str, Any]]
    usage: Mapping[str, Any]
    quota: BatchBotUsageSnapshot


class BatchBotService:
    """Coordinates Gemini calls, contextual data, and automation hooks."""

    def __init__(self, user):
        if not user or not getattr(user, "organization", None):
            raise BatchBotServiceError("BatchBot requires an authenticated organization user.")

        self.user = user
        self.organization = user.organization
        self.config = current_app.config
        self.client = GoogleAIClient.from_app()
        self.model_name = (
            self.config.get("GOOGLE_AI_BATCHBOT_MODEL")
            or self.config.get("GOOGLE_AI_DEFAULT_MODEL")
            or "gemini-1.5-pro"
        )

    def chat(
        self,
        *,
        prompt: str,
        history: Optional[Sequence[Mapping[str, str]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> BatchBotResponse:
        if not prompt:
            raise BatchBotServiceError("Prompt is required.")

        # Ensure quota is available before we attempt any work.
        BatchBotUsageService.ensure_within_limit(self.organization)

        contents = self._normalize_history(history)
        composed_prompt = self._compose_prompt(prompt, metadata)
        contents.append({"role": "user", "parts": [{"text": composed_prompt}]})

        result = self.client.generate_content(
            contents=contents,
            model=self.model_name,
            system_instruction=self._system_instruction(),
            tools=[{"function_declarations": self._function_declarations()}],
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "max_output_tokens": 1024,
            },
        )

        tool_results: List[Mapping[str, Any]] = []
        if result.tool_calls:
            for call in result.tool_calls:
                tool_results.append(self._execute_tool_call(call))

        usage_metadata = result.usage_metadata or {}
        quota = BatchBotUsageService.record_request(
            org=self.organization,
            user=self.user,
            metadata={
                "model": self.model_name,
                "finish_reason": result.finish_reason,
                "prompt_tokens": usage_metadata.get("prompt_token_count"),
                "candidate_tokens": usage_metadata.get("candidates_token_count"),
                "total_tokens": usage_metadata.get("total_token_count"),
                "tool_calls": len(tool_results),
            },
        )

        return BatchBotResponse(
            text=result.text,
            tool_results=tool_results,
            usage=usage_metadata,
            quota=quota,
        )

    # ------------------------------------------------------------------
    # Prompt + Context Builders
    # ------------------------------------------------------------------
    def _compose_prompt(self, prompt: str, metadata: Optional[Mapping[str, Any]]) -> str:
        context_blob = json.dumps(
            self._build_context_snapshot(metadata),
            default=_json_default,
        )
        instructions = (
            "Context Snapshot (JSON):\n"
            f"{context_blob}\n\n"
            "User Request:\n"
            f"{prompt.strip()}"
        )
        return instructions

    def _normalize_history(
        self, history: Optional[Sequence[Mapping[str, str]]]
    ) -> List[Mapping[str, Any]]:
        normalized: List[Mapping[str, Any]] = []
        if not history:
            return normalized
        for message in history:
            role = (message.get("role") or "").strip()
            content = message.get("content")
            if not role or not content:
                continue
            normalized.append({"role": role, "parts": [{"text": str(content)}]})
        return normalized

    def _build_context_snapshot(self, metadata: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
        inventory_items = (
            InventoryItem.query.filter_by(organization_id=self.organization.id)
            .order_by(asc(InventoryItem.quantity))
            .limit(6)
            .all()
        )

        recipes = (
            Recipe.query.filter_by(organization_id=self.organization.id)
            .order_by(desc(Recipe.updated_at))
            .limit(4)
            .all()
        )

        batches = (
            Batch.query.filter_by(organization_id=self.organization.id)
            .order_by(desc(Batch.created_at))
            .limit(4)
            .all()
        )

        return {
            "organization": {
                "id": self.organization.id,
                "name": self.organization.name,
                "subscription": getattr(self.organization.tier, "name", "unknown") if self.organization.tier else "trial",
            },
            "limits": {
                "max_batchbot_requests": getattr(self.organization.tier, "max_batchbot_requests", None),
            },
            "inventory_sample": [
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": _safe_float(item.quantity),
                    "unit": item.unit,
                    "type": item.type,
                    "category_id": item.category_id,
                    "cost_per_unit": _safe_float(item.cost_per_unit),
                    "is_perishable": getattr(item, "is_perishable", False),
                    "low_stock": bool(
                        item.quantity is not None
                        and item.quantity <= (getattr(item, "reorder_point", None) or 2)
                    ),
                }
                for item in inventory_items
            ],
            "recent_recipes": [
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "predicted_yield": _safe_float(recipe.predicted_yield),
                    "predicted_yield_unit": recipe.predicted_yield_unit,
                    "is_portioned": recipe.is_portioned,
                    "category_id": recipe.category_id,
                    "updated_at": _iso_dt(recipe.updated_at),
                }
                for recipe in recipes
            ],
            "recent_batches": [
                {
                    "id": batch.id,
                    "name": batch.name,
                    "status": batch.status,
                    "projected_yield": _safe_float(batch.projected_yield),
                    "projected_unit": batch.projected_yield_unit,
                    "created_at": _iso_dt(batch.created_at),
                    "finished_at": _iso_dt(batch.finished_at),
                }
                for batch in batches
            ],
            "metadata": metadata or {},
        }

    def _system_instruction(self) -> str:
        return (
            "You are Batchley, the AI copilot inside BatchTrack. "
            "You help makers run production by:\n"
            "- Translating messy instructions into structured inventory or recipe updates.\n"
            "- Suggesting process improvements grounded in the provided context.\n"
            "- Calling automation tools when the user explicitly asks you to execute a task.\n\n"
            "Automation guardrails:\n"
            "1. Only call a tool if the user gave enough detail (item name, quantities, etc.).\n"
            "2. If data is missing, ask a clarifying follow-up instead of guessing.\n"
            "3. When a tool call succeeds, summarize the outcome for the user.\n"
            "4. If a tool fails, explain why and provide next steps.\n"
            "5. Blend institutional knowledge from the context snapshot with public best practices when recommending improvements.\n"
            "6. The user interface is on Linux servers; any code snippet you output should be ready for Python 3 (Flask) or SQLAlchemy."
        )

    def _function_declarations(self) -> Sequence[Mapping[str, Any]]:
        return [
            {
                "name": "log_inventory_purchase",
                "description": "Restock an inventory item after a supplier delivery.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "inventory_item_id": {"type": "integer", "description": "Existing inventory item ID."},
                        "inventory_item_name": {"type": "string", "description": "Name search fallback when ID is unknown."},
                        "quantity": {"type": "number", "description": "Quantity purchased in the provided unit."},
                        "unit": {"type": "string", "description": "Unit matching the quantity provided. Defaults to the item's canonical unit."},
                        "cost_per_unit": {"type": "number", "description": "Optional cost override for this purchase."},
                        "notes": {"type": "string", "description": "Any note that should accompany the adjustment."},
                    },
                    "required": ["quantity"],
                },
            },
            {
                "name": "fetch_inventory_item",
                "description": "Fetch a detailed snapshot of a single inventory item.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "inventory_item_id": {"type": "integer"},
                        "inventory_item_name": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "name": "fetch_recipe_profile",
                "description": "Return the key data points for a recipe so you can reason about batching.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipe_id": {"type": "integer"},
                        "recipe_name": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "name": "fetch_report_snapshot",
                "description": "Return recent KPI-style insights (inventory valuation, batch velocity, low stock).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "report_type": {
                            "type": "string",
                            "enum": ["inventory_health", "batch_velocity", "costing"],
                            "description": "Pick the dataset you need.",
                        },
                    },
                    "required": [],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------
    def _execute_tool_call(self, call: Mapping[str, Any]) -> Mapping[str, Any]:
        name = call.get("name")
        raw_args = call.get("args") or {}

        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args

        handler = {
            "log_inventory_purchase": self._tool_log_inventory_purchase,
            "fetch_inventory_item": self._tool_fetch_inventory_item,
            "fetch_recipe_profile": self._tool_fetch_recipe_profile,
            "fetch_report_snapshot": self._tool_fetch_report_snapshot,
        }.get(name)

        if handler is None:
            return {
                "name": name,
                "arguments": args,
                "result": {"success": False, "error": f"Unknown tool '{name}'."},
            }

        try:
            result = handler(args or {})
        except Exception as exc:
            current_app.logger.exception("BatchBot tool failure: %s", name)
            result = {"success": False, "error": str(exc)}

        return {"name": name, "arguments": args, "result": result}

    def _tool_log_inventory_purchase(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        item = self._locate_inventory_item(
            item_id=args.get("inventory_item_id"),
            name=args.get("inventory_item_name"),
        )
        if not item:
            return {"success": False, "error": "Inventory item not found."}

        quantity = args.get("quantity")
        if quantity is None:
            return {"success": False, "error": "Quantity is required."}

        unit = args.get("unit") or item.unit
        cost_per_unit = args.get("cost_per_unit")
        notes = args.get("notes") or f"BatchBot restock logged by {self.user.full_name or self.user.username}"

        success, message = process_inventory_adjustment(
            item_id=item.id,
            change_type="restock",
            quantity=quantity,
            notes=notes,
            created_by=self.user.id,
            cost_override=cost_per_unit,
            unit=unit,
        )

        return {
            "success": bool(success),
            "message": message,
            "inventory_item": self._serialize_inventory_item(item),
        }

    def _tool_fetch_inventory_item(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        item = self._locate_inventory_item(
            item_id=args.get("inventory_item_id"),
            name=args.get("inventory_item_name"),
        )
        if not item:
            return {"success": False, "error": "Inventory item not found."}
        return {"success": True, "inventory_item": self._serialize_inventory_item(item)}

    def _tool_fetch_recipe_profile(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        recipe = self._locate_recipe(
            recipe_id=args.get("recipe_id"),
            name=args.get("recipe_name"),
        )
        if not recipe:
            return {"success": False, "error": "Recipe not found."}

        ingredients = []
        for ingredient in recipe.recipe_ingredients[:10]:
            ingredients.append(
                {
                    "id": ingredient.id,
                    "inventory_item_id": ingredient.inventory_item_id,
                    "name": ingredient.inventory_item.name if ingredient.inventory_item else None,
                    "quantity": _safe_float(ingredient.quantity),
                    "unit": ingredient.unit,
                }
            )

        return {
            "success": True,
            "recipe": {
                "id": recipe.id,
                "name": recipe.name,
                "predicted_yield": _safe_float(recipe.predicted_yield),
                "predicted_yield_unit": recipe.predicted_yield_unit,
                "is_portioned": recipe.is_portioned,
                "portion_name": recipe.portion_name,
                "portion_count": recipe.portion_count,
                "category_id": recipe.category_id,
                "updated_at": _iso_dt(recipe.updated_at),
                "ingredients": ingredients,
            },
        }

    def _tool_fetch_report_snapshot(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        report_type = args.get("report_type") or "inventory_health"
        inventory_items = (
            InventoryItem.query.filter_by(organization_id=self.organization.id)
            .order_by(asc(InventoryItem.quantity))
            .limit(25)
            .all()
        )

        total_quantity = sum(_safe_float(item.quantity) or 0 for item in inventory_items)
        total_value = sum(
            (_safe_float(item.quantity) or 0) * (_safe_float(item.cost_per_unit) or 0)
            for item in inventory_items
        )

        low_stock = [
            self._serialize_inventory_item(item) for item in inventory_items if (item.quantity or 0) <= 3
        ][:5]

        batches = (
            Batch.query.filter_by(organization_id=self.organization.id)
            .order_by(desc(Batch.created_at))
            .limit(10)
            .all()
        )

        batch_velocity = [
            {
                "id": batch.id,
                "name": batch.name,
                "status": batch.status,
                "created_at": _iso_dt(batch.created_at),
                "finished_at": _iso_dt(batch.finished_at),
            }
            for batch in batches
        ]

        payload = {
            "inventory_health": {
                "total_items": len(inventory_items),
                "total_quantity": total_quantity,
                "estimated_value": total_value,
                "lowest_stock_items": low_stock,
            },
            "batch_velocity": {
                "recent_batches": batch_velocity,
            },
            "costing": {
                "estimated_inventory_value": total_value,
                "average_cost_per_unit": (total_value / total_quantity) if total_quantity else None,
            },
        }

        return {"success": True, "report_type": report_type, "data": payload.get(report_type, payload["inventory_health"])}

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def _locate_inventory_item(self, *, item_id: Any, name: Any):
        query = InventoryItem.query.filter_by(organization_id=self.organization.id)
        if item_id:
            item = query.filter_by(id=item_id).first()
            if item:
                return item
        if name:
            term = f"%{name}%"
            return query.filter(InventoryItem.name.ilike(term)).first()
        return None

    def _locate_recipe(self, *, recipe_id: Any, name: Any):
        query = Recipe.query.filter_by(organization_id=self.organization.id)
        if recipe_id:
            recipe = query.filter_by(id=recipe_id).first()
            if recipe:
                return recipe
        if name:
            term = f"%{name}%"
            return query.filter(Recipe.name.ilike(term)).first()
        return None

    def _serialize_inventory_item(self, item: InventoryItem) -> Mapping[str, Any]:
        return {
            "id": item.id,
            "name": item.name,
            "quantity": _safe_float(item.quantity),
            "unit": item.unit,
            "type": item.type,
            "category_id": item.category_id,
            "cost_per_unit": _safe_float(item.cost_per_unit),
            "reorder_point": getattr(item, "reorder_point", None),
            "is_perishable": getattr(item, "is_perishable", False),
            "updated_at": _iso_dt(item.updated_at if hasattr(item, "updated_at") else None),
        }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_dt(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return TimezoneUtils.coerce_datetime(value).isoformat()
    except Exception:
        return None


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    try:
        return float(value)
    except Exception:
        return str(value)
