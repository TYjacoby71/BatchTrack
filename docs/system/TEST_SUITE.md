# Test Suite Overview

## Synopsis
Quick reference for what each automated test module exercises. Run tests with `make test` or `python -m pytest tests/ -v`.

## Glossary
- **Test module**: A single `tests/*.py` file exercising one domain or feature area.

| Test File | Purpose |
| --- | --- |
| `tests/developer/test_analytics_catalog.py` | Ensures developer-only analytics catalog view renders and respects permissions. |
| `tests/developer/test_developer_routes.py` | Covers the split developer blueprint controllers (users, orgs, container options) end-to-end. |
| `tests/developer/test_service_layers.py` | Unit-tests the new developer service helpers for organizations, users, and reference data. |
| `tests/test_auth_permissions.py` | Validates permission decorators and auth edge cases across the app. |
| `tests/test_batch_label_generator.py` | Verifies SKU/batch label generation helpers. |
| `tests/test_batch_label_uniqueness.py` | Guarantees batch labels remain unique under concurrency. |
| `tests/test_batchbot_jobs.py` | Exercises Batchbot job orchestration and status tracking. |
| `tests/test_billing_and_tier_enforcement.py` | Confirms billing state drives feature gating (including developer masquerade rules). |
| `tests/test_bulk_inventory_service.py` | Covers the bulk inventory adjustments service workflows. |
| `tests/test_container_auto_fill.py` | Tests container suggestion autofill logic in forms. |
| `tests/test_expiration_canonicalization.py` | Ensures expiration data is normalized across requests. |
| `tests/test_extras_expiration.py` | Validates extra batch item expiration handling. |
| `tests/test_global_link_drawer.py` | Tests the AI drawer responsible for global link recommendations. |
| `tests/test_google_oauth.py` | Covers Google OAuth login and callback flows. |
| `tests/test_help_routes_access.py` | Confirms in-app help pages enforce correct permissions. |
| `tests/test_inventory_adjustment_guardrails.py` | Verifies safety checks before inventory adjustments are applied. |
| `tests/test_inventory_adjustment_initial_stock.py` | Ensures initial stock adjustments behave correctly. |
| `tests/test_inventory_costing_toggle.py` | Tests toggling between costing strategies and resulting calculations. |
| `tests/test_inventory_fifo.py` | Exercises FIFO inventory math and persistence. |
| `tests/test_inventory_routes_canonicalization.py` | Validates canonical API payloads for inventory routes. |
| `tests/test_inventory_search_service.py` | Covers search helpers for inventory items. |
| `tests/test_plan_production_gating.py` | Ensures production planning respects permission gates. |
| `tests/test_plan_production_integration.py` | End-to-end test of production planning flows. |
| `tests/test_portioning_sku_derivation.py` | Validates SKU derivation for portioned products. |
| `tests/test_pos_integration_canonicalization.py` | Covers POS/Shopify integration payloads. |
| `tests/test_public_tools_access.py` | Verifies marketing calculators honor feature flags. |
| `tests/test_public_tools_and_exports_smoke.py` | Smoke-tests public tooling pages and export endpoints. |
| `tests/test_recipe_drafts.py` | Exercises draft recipe workflows. |
| `tests/test_recipe_marketplace_service.py` | Ensures the recipe marketplace service handles publishing and sales metadata. |
| `tests/test_recipe_origin.py` | Tests recipe lineage/origin tracking helpers. |
| `tests/test_recipe_service_workflows.py` | Full recipe service workflow coverage (create, edit, delete). |
| `tests/test_reservation_canonicalization.py` | Validates reservation API payload normalization. |
| `tests/test_retention_drawer.py` | Tests retention guidance drawer logic. |
| `tests/test_signup_stripe_flow.py` | Ensures Stripe signup flow is wired correctly. |
| `tests/test_signup_tiers.py` | Confirms tier selection and gating during signup. |
| `tests/test_single_session_enforcement.py` | Verifies single-session guard kicks users appropriately. |
| `tests/test_start_batch_integration.py` | Covers batch start automation and integrations. |
| `tests/test_stripe_webhooks.py` | Exercises Stripe webhook ingestion + validation. |
| `tests/test_timezone_conventions.py` | Guards against timezone regressions in models/helpers. |
