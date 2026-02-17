# LEGACY SHIM: This file provides a minimal shim for InventoryAlertService.
# Real functionality moved to combined_inventory_alerts.py

from __future__ import annotations

from typing import Iterable, Optional


class InventoryAlertService:
    """LEGACY SHIM: no-op compatibility surface for legacy imports."""

    @staticmethod
    def notify_if_low_stock(inventory_item_id: int) -> None:
        """No-op method for compatibility"""
        return

    @staticmethod
    def on_quantity_change(inventory_item_id: int) -> None:
        """No-op method for compatibility"""
        return

    @staticmethod
    def bulk_check_low_stock(organization_id: Optional[int] = None) -> list[int]:
        """No-op method for compatibility"""
        return []

    @staticmethod
    def trigger_low_stock_alerts(
        inventory_item_ids: Iterable[int] | None = None,
    ) -> None:
        """No-op method for compatibility"""
        return

    @staticmethod
    def get_low_stock_ingredients() -> list:
        """No-op method for compatibility"""
        return []

    @staticmethod
    def check_ingredient_stock_level(inventory_item_id: int) -> dict:
        """No-op method for compatibility"""
        return {"status": "ok", "level": "sufficient"}
