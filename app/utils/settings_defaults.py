from __future__ import annotations

import copy
from typing import Any, Dict

DEFAULT_APP_SETTINGS: Dict[str, Any] = {
    "low_stock_threshold": 5,
    "per_page": 20,
    "enable_csv_export": True,
    "alerts": {
        "max_dashboard_alerts": 3,
        "show_expiration_alerts": None,
        "show_timer_alerts": True,
        "show_low_stock_alerts": True,
        "show_batch_alerts": None,
        "show_fault_alerts": True,
        "low_stock_threshold": 5,
        "expiration_warning_days": 12,
        "show_inventory_refund": True,
        "show_alert_badges": True,
    },
    "batch_rules": {
        "require_timer_completion": False,
        "allow_intermediate_tags": True,
        "require_finish_confirmation": True,
        "stuck_batch_hours": 24,
    },
    "products": {
        "enable_variants": True,
        "show_profit_margins": True,
        "auto_generate_skus": False,
        "enable_product_images": True,
        "track_production_costs": True,
    },
    "display": {
        "per_page": 20,
        "enable_csv_export": True,
        "auto_save_forms": False,
        "dashboard_layout": "detailed",
        "show_quick_actions": False,
        "compact_view": False,
    },
    "recipe_builder": {
        "enable_variations": True,
        "enable_containers": True,
        "auto_scale_recipes": False,
        "show_cost_breakdown": True,
    },
    "inventory": {
        "enable_fifo_tracking": True,
        "show_expiration_dates": True,
        "auto_calculate_costs": True,
        "enable_barcode_scanning": False,
        "show_supplier_info": True,
        "enable_bulk_operations": True,
    },
    "accessibility": {
        "reduce_animations": False,
        "high_contrast_mode": False,
        "keyboard_navigation": False,
        "large_buttons": False,
    },
    "system": {
        "auto_backup": False,
        "log_level": "INFO",
        "per_page": 25,
        "enable_csv_export": True,
        "auto_save_forms": False,
    },
    "notifications": {
        "browser_notifications": True,
        "email_alerts": False,
        "alert_frequency": "real_time",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    },
}


def merge_settings_defaults(current: Dict[str, Any]) -> Dict[str, Any]:
    """Merge default settings without overwriting existing values."""

    def _merge(target: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        for key, value in defaults.items():
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                _merge(target[key], value)

    payload = dict(current or {})
    _merge(payload, DEFAULT_APP_SETTINGS)
    return payload
