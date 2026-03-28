"""Marketplace/POS integration models.

Synopsis:
Defines organization-scoped connection, mapping, webhook inbox, and sync-event
records used by Shopify/Etsy integration workflows.

Glossary:
- Connection: Authenticated link between an organization and a provider account.
- SKU map: Mapping between a BatchTrack SKU and provider identifiers.
- Webhook inbox: Durable storage for inbound provider events before processing.
"""

from __future__ import annotations

from app.extensions import db

from .mixins import ScopedModelMixin, TimestampMixin


class IntegrationConnection(ScopedModelMixin, TimestampMixin, db.Model):
    """Connected provider account for one organization."""

    __tablename__ = "integration_connection"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(32), nullable=False, index=True)  # shopify | etsy
    status = db.Column(
        db.String(32), nullable=False, default="disconnected"
    )  # connected | paused | error | disconnected
    account_label = db.Column(db.String(128), nullable=True)
    external_account_id = db.Column(db.String(128), nullable=True, index=True)
    external_shop_id = db.Column(db.String(128), nullable=True)
    external_shop_name = db.Column(db.String(160), nullable=True)

    access_token_encrypted = db.Column(db.Text, nullable=True)
    refresh_token_encrypted = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    scopes_csv = db.Column(db.Text, nullable=True)

    sync_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sync_prices = db.Column(db.Boolean, nullable=False, default=True)
    sync_quantities = db.Column(db.Boolean, nullable=False, default=True)
    sale_trigger_mode = db.Column(db.String(32), nullable=False, default="order_paid")
    return_mode = db.Column(db.String(32), nullable=False, default="manual")
    cancellation_mode = db.Column(db.String(32), nullable=False, default="manual")
    baseline_seed_mode = db.Column(
        db.String(32), nullable=False, default="batchtrack_to_channel"
    )

    metadata_json = db.Column(db.JSON, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_error_at = db.Column(db.DateTime, nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_integration_connection_org_provider",
        ),
        db.Index("ix_integration_connection_organization_id", "organization_id"),
        db.Index("ix_integration_connection_provider_status", "provider", "status"),
    )


class IntegrationLocationMap(ScopedModelMixin, TimestampMixin, db.Model):
    """Provider location records stored per organization connection."""

    __tablename__ = "integration_location"

    id = db.Column(db.Integer, primary_key=True)
    integration_connection_id = db.Column(
        db.Integer, db.ForeignKey("integration_connection.id"), nullable=False, index=True
    )
    provider = db.Column(db.String(32), nullable=False, index=True)
    external_location_id = db.Column(db.String(128), nullable=False, index=True)
    external_location_name = db.Column(db.String(160), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    metadata_json = db.Column(db.JSON, nullable=True)

    connection = db.relationship("IntegrationConnection", backref="location_maps")

    __table_args__ = (
        db.UniqueConstraint(
            "integration_connection_id",
            "external_location_id",
            name="uq_integration_location_connection_external_id",
        ),
        db.Index("ix_integration_location_org_provider", "organization_id", "provider"),
    )


class IntegrationSkuMap(ScopedModelMixin, TimestampMixin, db.Model):
    """Mapping between BatchTrack SKU records and provider listing/variant ids."""

    __tablename__ = "integration_sku_map"

    id = db.Column(db.Integer, primary_key=True)
    integration_connection_id = db.Column(
        db.Integer, db.ForeignKey("integration_connection.id"), nullable=False, index=True
    )
    product_sku_id = db.Column(
        db.Integer, db.ForeignKey("product_sku.id"), nullable=False, index=True
    )
    inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_item.id"), nullable=False, index=True
    )
    provider = db.Column(db.String(32), nullable=False, index=True)

    external_product_id = db.Column(db.String(128), nullable=True)
    external_variant_id = db.Column(db.String(128), nullable=True, index=True)
    external_listing_id = db.Column(db.String(128), nullable=True, index=True)
    external_sku_code = db.Column(db.String(128), nullable=True, index=True)
    integration_location_id = db.Column(
        db.Integer, db.ForeignKey("integration_location.id"), nullable=True, index=True
    )

    sync_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sync_price = db.Column(db.Boolean, nullable=False, default=True)
    sync_quantity = db.Column(db.Boolean, nullable=False, default=True)
    last_synced_price = db.Column(db.Float, nullable=True)
    last_synced_quantity = db.Column(db.Float, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_sync_direction = db.Column(db.String(32), nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)

    connection = db.relationship("IntegrationConnection", backref="sku_maps")

    __table_args__ = (
        db.UniqueConstraint(
            "integration_connection_id",
            "product_sku_id",
            name="uq_integration_sku_map_connection_sku",
        ),
        db.UniqueConstraint(
            "integration_connection_id",
            "external_variant_id",
            name="uq_integration_sku_map_connection_ext_variant",
        ),
        db.UniqueConstraint(
            "integration_connection_id",
            "external_listing_id",
            name="uq_integration_sku_map_connection_ext_listing",
        ),
        db.Index("ix_integration_sku_map_org_provider", "organization_id", "provider"),
        db.Index("ix_integration_sku_map_ext_sku_code", "external_sku_code"),
    )


class IntegrationWebhookInbox(ScopedModelMixin, TimestampMixin, db.Model):
    """Durable inbox for inbound provider webhook payloads."""

    __tablename__ = "integration_webhook_inbox"

    id = db.Column(db.Integer, primary_key=True)
    integration_connection_id = db.Column(
        db.Integer, db.ForeignKey("integration_connection.id"), nullable=True, index=True
    )
    provider = db.Column(db.String(32), nullable=False, index=True)
    event_type = db.Column(db.String(96), nullable=False, index=True)
    external_event_id = db.Column(db.String(128), nullable=True, index=True)
    external_order_id = db.Column(db.String(128), nullable=True)
    signature_valid = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    received_at = db.Column(db.DateTime, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    dedupe_key = db.Column(db.String(255), nullable=True)
    payload_json = db.Column(db.JSON, nullable=True)
    headers_json = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    connection = db.relationship("IntegrationConnection", backref="webhook_events")

    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "dedupe_key",
            name="uq_integration_webhook_inbox_provider_dedupe",
        ),
        db.Index(
            "ix_integration_webhook_inbox_org_provider_status",
            "organization_id",
            "provider",
            "status",
        ),
        db.Index(
            "ix_integration_webhook_inbox_external_order_id",
            "external_order_id",
        ),
    )


class IntegrationSyncEvent(ScopedModelMixin, TimestampMixin, db.Model):
    """Outbound/inbound sync operation log with retry metadata."""

    __tablename__ = "integration_sync_event"

    id = db.Column(db.Integer, primary_key=True)
    integration_connection_id = db.Column(
        db.Integer, db.ForeignKey("integration_connection.id"), nullable=False, index=True
    )
    provider = db.Column(db.String(32), nullable=False, index=True)
    direction = db.Column(db.String(16), nullable=False)  # inbound | outbound
    status = db.Column(db.String(32), nullable=False, default="pending")
    event_type = db.Column(db.String(96), nullable=False)
    correlation_id = db.Column(db.String(128), nullable=True)
    idempotency_key = db.Column(db.String(255), nullable=True)
    external_event_id = db.Column(db.String(128), nullable=True, index=True)
    external_order_id = db.Column(db.String(128), nullable=True)
    product_sku_id = db.Column(
        db.Integer, db.ForeignKey("product_sku.id"), nullable=True, index=True
    )
    inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_item.id"), nullable=True, index=True
    )
    quantity = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    payload_json = db.Column(db.JSON, nullable=True)
    result_json = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    processed_at = db.Column(db.DateTime, nullable=True)

    connection = db.relationship("IntegrationConnection", backref="sync_events")

    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "idempotency_key",
            name="uq_integration_sync_event_provider_idempotency_key",
        ),
        db.Index(
            "ix_integration_sync_event_org_provider_status",
            "organization_id",
            "provider",
            "status",
        ),
        db.Index("ix_integration_sync_event_external_order_id", "external_order_id"),
    )


class IntegrationOnboardingState(ScopedModelMixin, TimestampMixin, db.Model):
    """Per-organization provider onboarding checkpoint and resume state."""

    __tablename__ = "integration_onboarding_state"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(32), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="in_progress")
    current_stage = db.Column(db.String(64), nullable=False, default="provider_selection")
    stage_payload_json = db.Column(db.JSON, nullable=True)
    completed_stages_json = db.Column(db.JSON, nullable=True)
    last_checkpoint_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_integration_onboarding_state_org_provider",
        ),
        db.Index(
            "ix_integration_onboarding_state_org_status",
            "organization_id",
            "status",
        ),
    )
