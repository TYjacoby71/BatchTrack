"""POS/marketplace integration foundation schema.

Synopsis:
Adds core organization-scoped integration tables for provider connections,
location mapping, SKU mapping, webhook inbox storage, sync events, and
resumable onboarding state.

Glossary:
- Integration connection: OAuth/token-backed link to Shopify/Etsy per org.
- Webhook inbox: Durable staging table for inbound provider webhooks.
- SKU map: Mapping record between BatchTrack SKU and provider SKU/listing.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    safe_create_index,
    table_exists,
)


revision = "0034_pos_marketplace_integration"
down_revision = "0033_tool_feedback_note_persist"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("integration_connection"):
        op.create_table(
            "integration_connection",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="disconnected"),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("external_account_id", sa.String(length=128), nullable=True),
            sa.Column("external_shop_id", sa.String(length=128), nullable=True),
            sa.Column("external_shop_name", sa.String(length=160), nullable=True),
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("scopes_csv", sa.Text(), nullable=True),
            sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_prices", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_quantities", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sale_trigger_mode", sa.String(length=32), nullable=False, server_default="order_paid"),
            sa.Column("return_mode", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("cancellation_mode", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("baseline_seed_mode", sa.String(length=32), nullable=False, server_default="batchtrack_to_channel"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_connection_organization_id",
            ),
            sa.UniqueConstraint(
                "organization_id",
                "provider",
                name="uq_integration_connection_org_provider",
            ),
        )
        safe_create_index(
            "ix_integration_connection_organization_id",
            "integration_connection",
            ["organization_id"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_connection_provider_status",
            "integration_connection",
            ["provider", "status"],
            verbose=False,
        )

    if not table_exists("integration_location_map"):
        op.create_table(
            "integration_location_map",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_location_id", sa.String(length=128), nullable=False),
            sa.Column("provider_location_name", sa.String(length=255), nullable=False),
            sa.Column("provider_location_code", sa.String(length=128), nullable=True),
            sa.Column("bt_location_key", sa.String(length=128), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["integration_connection.id"],
                name="fk_integration_location_map_connection_id",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_location_map_organization_id",
            ),
            sa.UniqueConstraint(
                "connection_id",
                "provider_location_id",
                name="uq_integration_location_map_connection_provider_location",
            ),
        )
        safe_create_index(
            "ix_integration_location_map_org_provider",
            "integration_location_map",
            ["organization_id", "provider"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_location_map_bt_location_key",
            "integration_location_map",
            ["bt_location_key"],
            verbose=False,
        )

    if not table_exists("integration_sku_map"):
        op.create_table(
            "integration_sku_map",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("product_sku_id", sa.Integer(), nullable=False),
            sa.Column("provider_product_id", sa.String(length=128), nullable=True),
            sa.Column("provider_variant_id", sa.String(length=128), nullable=True),
            sa.Column("provider_listing_id", sa.String(length=128), nullable=True),
            sa.Column("provider_sku_code", sa.String(length=128), nullable=True),
            sa.Column("provider_location_id", sa.String(length=128), nullable=True),
            sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_price", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_quantity", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sync_status", sa.String(length=32), nullable=True, server_default="pending"),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["integration_connection.id"],
                name="fk_integration_sku_map_connection_id",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_sku_map_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["product_sku_id"],
                ["product_sku.id"],
                name="fk_integration_sku_map_product_sku_id",
            ),
            sa.UniqueConstraint(
                "connection_id",
                "product_sku_id",
                name="uq_integration_sku_map_connection_sku",
            ),
        )
        safe_create_index(
            "ix_integration_sku_map_org_provider",
            "integration_sku_map",
            ["organization_id", "provider"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sku_map_provider_variant_id",
            "integration_sku_map",
            ["provider_variant_id"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sku_map_provider_listing_id",
            "integration_sku_map",
            ["provider_listing_id"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sku_map_provider_sku_code",
            "integration_sku_map",
            ["provider_sku_code"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sku_map_provider_location_id",
            "integration_sku_map",
            ["provider_location_id"],
            verbose=False,
        )

    if not table_exists("integration_webhook_inbox"):
        op.create_table(
            "integration_webhook_inbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("connection_id", sa.Integer(), nullable=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column("external_event_id", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("signature_header", sa.String(length=512), nullable=True),
            sa.Column("signature_valid", sa.Boolean(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processing_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["integration_connection.id"],
                name="fk_integration_webhook_inbox_connection_id",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_webhook_inbox_organization_id",
            ),
            sa.UniqueConstraint(
                "idempotency_key",
                name="uq_integration_webhook_inbox_idempotency_key",
            ),
        )
        safe_create_index(
            "ix_integration_webhook_inbox_org_provider_status",
            "integration_webhook_inbox",
            ["organization_id", "processing_status"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_webhook_inbox_provider_external_event",
            "integration_webhook_inbox",
            ["provider", "external_event_id"],
            verbose=False,
        )

    if not table_exists("integration_sync_event"):
        op.create_table(
            "integration_sync_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("sku_map_id", sa.Integer(), nullable=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
            sa.Column("external_event_id", sa.String(length=128), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("response_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["integration_connection.id"],
                name="fk_integration_sync_event_connection_id",
            ),
            sa.ForeignKeyConstraint(
                ["sku_map_id"],
                ["integration_sku_map.id"],
                name="fk_integration_sync_event_sku_map_id",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_sync_event_organization_id",
            ),
        )
        safe_create_index(
            "ix_integration_sync_event_org_provider_status",
            "integration_sync_event",
            ["organization_id", "status"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sync_event_provider_direction",
            "integration_sync_event",
            ["provider", "direction"],
            verbose=False,
        )
        safe_create_index(
            "ix_integration_sync_event_idempotency_key",
            "integration_sync_event",
            ["idempotency_key"],
            verbose=False,
        )

    if not table_exists("integration_onboarding_state"):
        op.create_table(
            "integration_onboarding_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("current_stage_key", sa.String(length=64), nullable=False, server_default="start"),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("stage_payload_json", sa.JSON(), nullable=True),
            sa.Column("completed_stages_json", sa.JSON(), nullable=True),
            sa.Column("last_checkpoint_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_integration_onboarding_state_organization_id",
            ),
            sa.UniqueConstraint(
                "organization_id",
                "provider",
                name="uq_integration_onboarding_state_org_provider",
            ),
        )
        safe_create_index(
            "ix_integration_onboarding_state_org_provider",
            "integration_onboarding_state",
            ["organization_id", "provider"],
            verbose=False,
        )


def downgrade():
    for table_name in (
        "integration_onboarding_state",
        "integration_sync_event",
        "integration_webhook_inbox",
        "integration_sku_map",
        "integration_location_map",
        "integration_connection",
    ):
        if table_exists(table_name):
            op.drop_table(table_name)
