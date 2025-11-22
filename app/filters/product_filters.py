from __future__ import annotations

import re
from typing import Any, Dict, Mapping, MutableMapping

from flask import Flask

ParsedSaleData = Dict[str, str | None]

SALE_DATA_FIELDS = ("quantity", "sale_price", "customer", "notes")
SALE_FIELD_TEMPLATE: Mapping[str, None] = dict.fromkeys(SALE_DATA_FIELDS)  # type: ignore[arg-type]


def register_product_filters(app: Flask) -> None:
    """Attach product-related template filters to the given Flask application."""

    @app.template_filter("parse_sale_data")
    def parse_sale_data(note: str | None) -> ParsedSaleData:
        """Extract structured metadata from serialized sale notes."""
        data: MutableMapping[str, str | None] = dict(SALE_FIELD_TEMPLATE)
        if not note:
            return data  # type: ignore[return-value]

        fifo_match = re.search(r"FIFO deduction:\s*([\d.]+)\s*\w+", note)
        if fifo_match:
            data["quantity"] = fifo_match.group(1)

        sale_match = re.search(r"Sale:\s*([\d.]+)\s*×.*?for\s*\$?([\d.]+)", note)
        if sale_match:
            data["quantity"] = sale_match.group(1)
            data["sale_price"] = f"${sale_match.group(2)}"

        customer_match = re.search(r"to\s+(.+?)(?:\.|$)", note)
        if customer_match:
            data["customer"] = customer_match.group(1).strip()

        if not any(data[field] for field in ("quantity", "sale_price", "customer")):
            data["notes"] = note
        return data  # type: ignore[return-value]


def product_variant_name(sku: Any) -> str:
    """Return a display-friendly name for a product SKU/variant reference."""
    if not sku:
        return ""

    if getattr(sku, "variant", None):
        product_name = getattr(getattr(sku, "product", None), "name", "")
        variant_name = getattr(getattr(sku, "variant", None), "name", "")
        return f"{product_name} - {variant_name}".strip(" -")

    if getattr(sku, "variant_name", None):
        product_name = getattr(sku, "product_name", "") or getattr(getattr(sku, "product", None), "name", "")
        return f"{product_name} - {sku.variant_name}".strip(" -")

    return getattr(sku, "product_name", None) or str(sku)


def ingredient_cost_currency(cost: Any) -> str:
    """Format ingredient cost as currency."""
    try:
        value = float(cost)
    except (TypeError, ValueError):
        value = 0.0
    return f"${value:.2f}"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float with fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def register_filters(app: Flask) -> None:
    """Register every template filter for product-facing templates."""
    register_product_filters(app)

    @app.template_filter("get_fifo_summary")
    def get_fifo_summary_filter(_inventory_id: Any) -> None:
        """Historical filter placeholder; FIFO summaries now deprecated."""
        return None
