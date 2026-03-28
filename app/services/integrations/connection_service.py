"""Integration connection service boundary.

Synopsis:
Provides organization-scoped read/write helpers for marketplace integration
connections, location maps, and high-level dashboard status payloads.

Glossary:
- Connection: Provider link record for an organization.
- Location map: External location metadata persisted for mapping.
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import (
    IntegrationConnection,
    IntegrationLocationMap,
    IntegrationOnboardingState,
    IntegrationSkuMap,
    IntegrationSyncEvent,
)


class IntegrationConnectionService:
    """Service helpers for integration connection records."""

    @staticmethod
    def list_connections(organization_id: int) -> list[IntegrationConnection]:
        return (
            IntegrationConnection.query.filter_by(organization_id=organization_id)
            .order_by(IntegrationConnection.provider.asc())
            .all()
        )

    @staticmethod
    def get_connection(
        organization_id: int, provider: str
    ) -> IntegrationConnection | None:
        return IntegrationConnection.query.filter_by(
            organization_id=organization_id,
            provider=(provider or "").strip().lower(),
        ).first()

    @staticmethod
    def list_connections_for_org(org_id: int) -> list[IntegrationConnection]:
        """Compatibility alias used by organization dashboard routes."""
        return IntegrationConnectionService.list_connections(organization_id=org_id)

    @staticmethod
    def upsert_connection(
        *,
        organization_id: int,
        provider: str,
        status: str = "disconnected",
        account_label: str | None = None,
    ) -> IntegrationConnection:
        normalized_provider = (provider or "").strip().lower()
        connection = IntegrationConnectionService.get_connection(
            organization_id=organization_id,
            provider=normalized_provider,
        )
        if connection is None:
            connection = IntegrationConnection(
                organization_id=organization_id,
                provider=normalized_provider,
                status=status,
                account_label=account_label,
            )
            db.session.add(connection)
        else:
            connection.status = status
            if account_label is not None:
                connection.account_label = account_label
        db.session.commit()
        return connection

    @staticmethod
    def list_location_maps(
        organization_id: int,
        *,
        provider: str | None = None,
    ) -> list[IntegrationLocationMap]:
        query = IntegrationLocationMap.query.filter_by(organization_id=organization_id)
        if provider:
            query = query.filter_by(provider=(provider or "").strip().lower())
        return query.order_by(
            IntegrationLocationMap.provider.asc(),
            IntegrationLocationMap.provider_location_name.asc(),
        ).all()

    @staticmethod
    def get_connection_summary(org_id: int) -> dict[str, Any]:
        """Compatibility alias used by org integration status endpoint."""
        return IntegrationConnectionService.build_dashboard_status(organization_id=org_id)

    @staticmethod
    def get_onboarding_summary(org_id: int) -> dict[str, dict[str, Any]]:
        """Return stage + completion details keyed by provider."""
        states = IntegrationOnboardingState.query.filter_by(organization_id=org_id).all()
        default = {
            "shopify": {
                "provider": "shopify",
                "current_stage": "not_started",
                "is_completed": False,
                "completed_stages_count": 0,
                "last_checkpoint_at": None,
            },
            "etsy": {
                "provider": "etsy",
                "current_stage": "not_started",
                "is_completed": False,
                "completed_stages_count": 0,
                "last_checkpoint_at": None,
            },
        }
        for state in states:
            provider = (state.provider or "").strip().lower()
            if provider not in default:
                continue
            completed = state.completed_stages_json or []
            default[provider].update(
                {
                    "current_stage": state.current_stage_key or "not_started",
                    "is_completed": bool(state.is_completed),
                    "completed_stages_count": len(completed)
                    if isinstance(completed, list)
                    else 0,
                    "last_checkpoint_at": (
                        state.last_checkpoint_at.isoformat()
                        if state.last_checkpoint_at
                        else None
                    ),
                }
            )
        return default

    @staticmethod
    def build_pos_provider_cards(org_id: int) -> list[dict[str, Any]]:
        """Build provider cards for dashboard POS tab shell."""
        summary = IntegrationConnectionService.get_connection_summary(org_id=org_id)
        providers = summary.get("providers", [])
        onboarding = IntegrationConnectionService.get_onboarding_summary(org_id=org_id)
        cards: list[dict[str, Any]] = []
        for item in providers:
            provider = (item.get("provider") or "").strip().lower()
            if provider not in {"shopify", "etsy"}:
                continue
            mapped_skus = IntegrationSkuMap.query.filter_by(
                organization_id=org_id,
                provider=provider,
                sync_enabled=True,
            ).count()
            failed_sync_events = IntegrationSyncEvent.query.filter_by(
                organization_id=org_id,
                provider=provider,
                status="failed",
            ).count()
            cards.append(
                {
                    "provider": provider,
                    "label": "Shopify" if provider == "shopify" else "Etsy",
                    "description": (
                        "Sync products, prices, quantities, and order hooks."
                        if provider == "shopify"
                        else "Sync listings, prices, quantities, and order hooks."
                    ),
                    "connected": bool(item.get("connected")),
                    "status": item.get("status") or "not_connected",
                    "location_count": item.get("location_count") or 0,
                    "mapped_skus": mapped_skus,
                    "failed_sync_events": failed_sync_events,
                    "onboarding_stage": onboarding.get(provider, {}).get("current_stage")
                    or "not_started",
                    "last_successful_sync": item.get("last_sync_at"),
                }
            )
        return cards

    @staticmethod
    def build_dashboard_status(organization_id: int) -> dict[str, Any]:
        connections = IntegrationConnectionService.list_connections(organization_id)
        location_maps = IntegrationConnectionService.list_location_maps(organization_id)

        provider_payload: dict[str, dict[str, Any]] = {}
        for provider in ("shopify", "etsy"):
            provider_payload[provider] = {
                "provider": provider,
                "connected": False,
                "status": "not_connected",
                "connection_id": None,
                "display_name": None,
                "external_shop_name": None,
                "external_shop_domain": None,
                "last_sync_at": None,
                "last_error": None,
                "location_count": 0,
            }

        for connection in connections:
            provider_key = (connection.provider or "").strip().lower()
            if provider_key not in provider_payload:
                continue
            provider_payload[provider_key].update(
                {
                    "connected": connection.status == "connected",
                    "status": connection.status,
                    "connection_id": connection.id,
                    "display_name": connection.account_label,
                    "external_shop_name": connection.external_shop_name,
                    "external_shop_domain": connection.external_shop_url,
                    "last_sync_at": (
                        connection.last_sync_at.isoformat()
                        if connection.last_sync_at
                        else None
                    ),
                    "last_error": None,
                }
            )

        for location in location_maps:
            provider_key = (location.provider or "").strip().lower()
            if provider_key in provider_payload:
                provider_payload[provider_key]["location_count"] += 1

        providers = [provider_payload["shopify"], provider_payload["etsy"]]
        return {
            "organization_id": organization_id,
            "providers": providers,
            "connected_count": sum(1 for item in providers if item["connected"]),
        }
