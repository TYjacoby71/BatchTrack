"""Integration registry definitions.

Synopsis:
Defines known integrations and their configuration requirements.

Glossary:
- Integration: External system connected to BatchTrack.
- Spec: Metadata describing integration requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from flask import current_app


# --- IntegrationSpec ---
# Purpose: Describe required metadata for one integration.
@dataclass(frozen=True)
class IntegrationSpec:
    key: str
    label: str
    description: str
    category: str
    status: str
    required_env: tuple[str, ...] = ()
    optional_env: tuple[str, ...] = ()
    permission: Optional[str] = None
    toggleable: bool = False
    toggle_endpoint: Optional[str] = None
    notes: Optional[str] = None


# --- Resolve config value ---
# Purpose: Fetch config values for integration checks.
def _env_or_config_value(key: str) -> Optional[str]:
    return current_app.config.get(key)


# --- Integration specs ---
# Purpose: Enumerate known integrations and their requirements.
def _specs() -> Iterable[IntegrationSpec]:
    return [
        IntegrationSpec(
            key="shopify",
            label="Shopify",
            description="POS/Shopify integration (stubbed).",
            category="Commerce & Marketplace",
            status="stub",
            permission="integrations.shopify",
        ),
        IntegrationSpec(
            key="etsy",
            label="Etsy",
            description="Marketplace sync for Etsy (stubbed).",
            category="Commerce & Marketplace",
            status="stub",
            permission="integrations.marketplace",
        ),
        IntegrationSpec(
            key="api_access",
            label="Public API Access",
            description="REST API access for third-party apps.",
            category="Commerce & Marketplace",
            status="stub",
            permission="integrations.api_access",
        ),
        IntegrationSpec(
            key="oauth",
            label="OAuth Login Providers",
            description="Google OAuth login support.",
            category="Authentication",
            status="wired",
            required_env=("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
        ),
        IntegrationSpec(
            key="auto_backup",
            label="Auto Backup System",
            description="Nightly exports of core tables and settings.",
            category="Automation",
            status="stub",
            toggleable=True,
            toggle_endpoint="developer.integrations_set_auto_backup",
        ),
    ]


# --- Build integration categories ---
# Purpose: Group integrations for UI display by category.
def build_integration_categories(
    *, auto_backup_enabled: bool = False
) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for spec in _specs():
        required_env = list(spec.required_env)
        optional_env = list(spec.optional_env)
        ready = True
        if required_env:
            ready = all(bool(_env_or_config_value(key)) for key in required_env)
        item = {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "status": spec.status,
            "required_env": required_env,
            "optional_env": optional_env,
            "permission": spec.permission,
            "ready": ready,
            "toggleable": spec.toggleable,
            "toggle_endpoint": spec.toggle_endpoint,
            "enabled": auto_backup_enabled if spec.key == "auto_backup" else None,
            "notes": spec.notes,
        }
        grouped.setdefault(spec.category, []).append(item)

    return [{"title": title, "items": items} for title, items in grouped.items()]
