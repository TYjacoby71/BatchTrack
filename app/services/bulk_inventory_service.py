from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models import InventoryItem
from app.services.analytics_tracking_service import AnalyticsTrackingService
from app.services.inventory_adjustment import (
    create_inventory_item,
    process_inventory_adjustment,
)


class BulkInventoryServiceError(RuntimeError):
    """Raised when bulk inventory operations cannot be performed."""


class BulkInventoryAbortError(BulkInventoryServiceError):
    """Raised when a bulk submission must be aborted atomically."""

    def __init__(self, message: str, *, context: Mapping[str, Any]):
        super().__init__(message)
        self.context = context


class BulkInventoryService:
    """Orchestrates multi-line inventory updates independent of BatchBot."""

    SUPPORTED_CHANGE_TYPES = {"create", "restock", "spoil", "trash"}

    def __init__(self, *, organization_id: int | None, user):
        if not organization_id:
            raise BulkInventoryServiceError(
                "Organization context is required for bulk inventory updates."
            )
        self.organization_id = organization_id
        self.user = user

    def submit_bulk_inventory_update(
        self,
        lines: Sequence[Mapping[str, Any]] | None,
        *,
        submit_now: bool = True,
        note_builder: Optional[
            Callable[[str, InventoryItem, Mapping[str, Any]], str]
        ] = None,
    ) -> Mapping[str, Any]:
        """Normalize incoming lines and optionally execute adjustments immediately."""
        normalized = [self._normalize_line(entry) for entry in (lines or []) if entry]
        if not normalized:
            return {"success": False, "error": "No lines supplied."}

        if not submit_now:
            return {"success": True, "draft": normalized}

        results: list[MutableMapping[str, Any]] = []
        pending_events: list[Mapping[str, Any]] = []

        try:
            for idx, line in enumerate(normalized, start=1):
                change_type = (line["change_type"] or "").lower()
                target_change_type = self._map_change_type(change_type)
                quantity = line.get("quantity")
                if quantity is None or quantity <= 0:
                    raise self._abort(
                        idx, line, change_type, "quantity must be greater than zero."
                    )

                try:
                    item, _ = self._ensure_inventory_item(line, auto_commit=False)
                except BulkInventoryServiceError as exc:
                    raise self._abort(idx, line, change_type, str(exc))

                unit = line.get("unit") or item.unit or "gram"
                cost_entry_type = (line.get("cost_entry_type") or "no_change").lower()
                if cost_entry_type not in {"no_change", "per_unit", "total"}:
                    cost_entry_type = "no_change"
                raw_cost = line.get("cost_per_unit")
                cost_override = None
                if cost_entry_type != "no_change" and raw_cost is not None:
                    if cost_entry_type == "total":
                        if quantity <= 0:
                            raise self._abort(
                                idx,
                                line,
                                change_type,
                                "total cost requires a positive quantity.",
                            )
                        cost_override = raw_cost / quantity
                    else:
                        cost_override = raw_cost
                resolved_notes = line.get("notes")
                if not resolved_notes and note_builder:
                    resolved_notes = note_builder(change_type, item, line)
                if not resolved_notes:
                    resolved_notes = f"Bulk update ({change_type})"

                created_by = getattr(self.user, "id", None)
                adjustment_result = process_inventory_adjustment(
                    item_id=item.id,
                    change_type=target_change_type,
                    quantity=quantity,
                    notes=resolved_notes,
                    created_by=created_by,
                    cost_override=cost_override,
                    unit=unit,
                    defer_commit=True,
                    include_event_payload=True,
                )
                success, message, event_payload = self._unpack_adjustment_result(
                    adjustment_result
                )
                if not success:
                    raise self._abort(
                        idx, {"inventory_item_name": item.name}, change_type, message
                    )

                pending_events.append(event_payload)
                results.append(
                    {
                        "line": idx,
                        "item_id": item.id,
                        "item_name": item.name,
                        "change_type": change_type,
                        "success": True,
                        "message": message,
                    }
                )

            db.session.commit()
        except BulkInventoryAbortError as exc:
            db.session.rollback()
            response = {
                "success": False,
                "error": str(exc),
                "failed_line": exc.context.get("line"),
                "failed_change_type": exc.context.get("change_type"),
                "failed_item_name": exc.context.get("item_name"),
            }
            return response
        except Exception:
            db.session.rollback()
            try:
                current_app.logger.exception("Bulk inventory update failed")
            except Exception:
                pass
            return {
                "success": False,
                "error": "Bulk inventory aborted due to an unexpected error. Please try again.",
            }

        self._emit_events(pending_events)
        return {"success": True, "results": results}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_line(self, raw: Mapping[str, Any]) -> MutableMapping[str, Any]:
        return {
            "inventory_item_id": _safe_int(raw.get("inventory_item_id")),
            "inventory_item_name": _clean_string(
                raw.get("inventory_item_name") or raw.get("name")
            ),
            "inventory_type": _clean_string(
                raw.get("inventory_type") or raw.get("type")
            )
            or "ingredient",
            "change_type": (_clean_string(raw.get("change_type")) or "").lower(),
            "quantity": _safe_float(raw.get("quantity")),
            "unit": _clean_string(raw.get("unit")),
            "cost_per_unit": _safe_float(raw.get("cost_per_unit")),
            "cost_entry_type": _clean_string(raw.get("cost_entry_type")),
            "notes": _clean_string(raw.get("notes")),
            "allow_create": bool(raw.get("allow_create"))
            or (_clean_string(raw.get("change_type")) == "create"),
            "global_item_id": _safe_int(raw.get("global_item_id")),
        }

    def _ensure_inventory_item(
        self, descriptor: Mapping[str, Any], *, auto_commit: bool = True
    ):
        query = InventoryItem.query.filter(
            InventoryItem.organization_id == self.organization_id,
            InventoryItem.is_archived != True,  # noqa: E712
        )

        item_id = descriptor.get("inventory_item_id")
        if item_id:
            item = query.filter(InventoryItem.id == item_id).first()
            if item:
                return item, False

        name = descriptor.get("inventory_item_name")
        if name:
            normalized = name.lower()
            item = (
                query.filter(func.lower(InventoryItem.name) == normalized)
                .filter(~InventoryItem.type.in_(("product", "product-reserved")))
                .first()
            )
            if item:
                return item, False

        if not descriptor.get("allow_create"):
            label = name or (f"#{item_id}" if item_id else "selected item")
            raise BulkInventoryServiceError(
                f"Inventory item '{label}' was not found and creation was not permitted."
            )

        return self._create_inventory_item(descriptor, auto_commit=auto_commit)

    def _create_inventory_item(
        self, descriptor: Mapping[str, Any], *, auto_commit: bool = True
    ):
        form_data = {
            "name": descriptor.get("inventory_item_name") or "Untitled Item",
            "type": descriptor.get("inventory_type") or "ingredient",
            "unit": descriptor.get("unit") or "gram",
            "quantity": "",
            "cost_per_unit": (
                ""
                if descriptor.get("cost_per_unit") is None
                else str(descriptor.get("cost_per_unit"))
            ),
            "cost_entry_type": descriptor.get("cost_entry_type") or "per_unit",
            "notes": descriptor.get("notes") or "",
        }
        if descriptor.get("global_item_id"):
            form_data["global_item_id"] = descriptor["global_item_id"]

        success, message, new_item_id = create_inventory_item(
            form_data=form_data,
            organization_id=self.organization_id,
            created_by=getattr(self.user, "id", None),
            auto_commit=auto_commit,
        )
        if not success or not new_item_id:
            raise BulkInventoryServiceError(
                message or f"Failed to create inventory item '{form_data['name']}'."
            )

        item = db.session.get(InventoryItem, int(new_item_id))
        if not item:
            raise BulkInventoryServiceError(
                "Newly created inventory item could not be loaded."
            )
        return item, True

    def _map_change_type(self, change_type: str) -> str:
        normalized = (change_type or "").lower()
        if normalized not in self.SUPPORTED_CHANGE_TYPES:
            raise BulkInventoryServiceError(
                f"Unsupported bulk change type '{change_type}'."
            )
        mapping = {
            "create": "restock",
            "restock": "restock",
            "spoil": "spoil",
            "trash": "trash",
        }
        return mapping[normalized]

    def _unpack_adjustment_result(
        self, result: Any
    ) -> tuple[bool, str, Optional[Mapping[str, Any]]]:
        if isinstance(result, (list, tuple)):
            if len(result) == 3:
                return result  # success, message, payload
            if len(result) == 2:
                success, message = result
                return success, message, None
        return False, "Adjustment returned an unexpected response.", None

    def _emit_events(self, entries: Sequence[Optional[Mapping[str, Any]]]) -> None:
        for payload in entries:
            if not payload:
                continue
            AnalyticsTrackingService.emit(**payload, auto_commit=False)

    def _abort(
        self, line_number: int, line: Mapping[str, Any], change_type: str, reason: str
    ) -> BulkInventoryAbortError:
        item_label = line.get("inventory_item_name") or "selected item"
        action = self._describe_action(change_type)
        message = (
            f"Bulk inventory aborted: there was an error {action} '{item_label}' on line {line_number} "
            f"because {reason}. No changes were applied. Please resolve the issue and try again."
        )
        context = {
            "line": line_number,
            "change_type": change_type,
            "item_name": item_label,
        }
        return BulkInventoryAbortError(message, context=context)

    def _describe_action(self, change_type: str) -> str:
        if change_type == "create":
            return "creating"
        if change_type:
            return f"adjusting ({change_type})"
        return "adjusting"


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
