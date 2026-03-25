# Parallel Flags Tracker (Boundary Program)

Purpose: track non-blocking risks discovered while extracting blueprint boundary violations so adjacent hardening work can run in parallel.

## Open flags

1. **Auth token flow duplication across modules**
   - **Surface:** `app/services/signup_service.py`, `app/services/user_invite_service.py`, `app/services/auth_account_service.py`
   - **Flag:** verification/reset token field writes now exist in multiple services; this can drift unless a single token-lifecycle authority is adopted.
   - **Parallel action:** centralize token issuance/clear semantics in one service and migrate invite/signup writers to use it.
   - **Status:** open

2. **Developer support submissions shaping remains route-local**
   - **Surface:** `app/blueprints/developer/views/organization_routes.py`
   - **Flag:** support submissions route still owns substantial grouping/selection shaping and should move behind a service boundary over time.
   - **Parallel action:** extract support-submissions grouping/selection pipeline into a dedicated developer support service.
   - **Status:** open

3. **Known integration posture still incomplete**
   - **Surface:** `app/services/whop_service.py`, `app/services/billing_service.py`, `app/services/pos_integration.py`, soap push UI flow
   - **Flag:** Whop and Soap push remain partial/stubbed, and POS production module still embeds mock/test classes.
   - **Parallel action:** execute Workstream C items from boundary report + consolidated backlog.
   - **Status:** open

## Recently closed flags

- **Settings routes retained direct ORM/session access across user preferences/profile/password/bulk-update/user-management flows**
  - **Closed by:** moving user preference retrieval/mutation, profile/password persistence, bulk inventory/container updates, timezone updates, and user-management user-list queries behind `app/services/settings_route_service.py`.
  - **Routes affected:** `app/blueprints/settings/routes.py` (`get_user_preferences`, `update_user_preferences`, `save_profile`, `change_password`, `set_backup_password`, `bulk_update_ingredients`, `bulk_update_containers`, `update_timezone`, `update_user_preference`, `user_management`)

- **Product variants routes retained direct ORM/session access across add/view/create-sku/edit/delete flows**
  - **Closed by:** moving product/variant/SKU/container lookups, variant/SKU creation mutations, variant update/deactivation, base-variant fallback creation, and rollback handling into `app/services/product_variant_route_service.py`.
  - **Routes affected:** `app/blueprints/products/product_variants.py` (`add_variant`, `view_variant`, `create_sku_for_variant`, `edit_variant`, `delete_variant`)

- **Auth login/quick-signup routes retained direct ORM/session access**
  - **Closed by:** moving login-user lookup, verification token persistence, login commit/rollback helpers, free-tier resolution, quick-signup org/user creation, global-item lookup, and logout token-clear session handling into `app/services/auth_login_route_service.py`.
  - **Routes affected:** `app/blueprints/auth/login_routes.py` (`_send_verification_if_needed`, `login`, `quick_signup`, `logout`)

- **Ingredient API route-local ORM/session access across category/search/create-link flows**
  - **Closed by:** moving ingredient category lookups, ingredient/form/variation/global-item search pipelines, and create-or-link inventory mutation/session handling into `app/services/ingredient_route_service.py`.
  - **Routes affected:** `app/blueprints/api/ingredient_routes.py` (`get_categories`, `get_ingredient_density`, `search_ingredients`, `search_ingredient_definitions`, `list_forms_for_ingredient_definition`, `search_physical_forms`, `search_variations`, `create_or_link_ingredient`, `search_global_items`)

- **Recipe manage routes retained direct ORM/session access across list/view/note/lock/make-parent flows**
  - **Closed by:** moving recipe list pagination/grouped variations, view-note/group-version lookups, note insertion, lock/unlock persistence, and legacy make-parent conversion/session handling into `app/services/recipe_manage_view_service.py`.
  - **Routes affected:** `app/blueprints/recipes/views/manage_routes.py` (`list_recipes`, `view_recipe`, `add_recipe_note`, `make_parent_recipe`, `lock_recipe`, `unlock_recipe`)

- **SKU route-local ORM/session access across view/edit/merge flows**
  - **Closed by:** moving SKU lookup/history queries, lot/history/reservation updates, and route-level commit/rollback handling into `app/services/sku_route_service.py`.
  - **Routes affected:** `app/blueprints/products/sku.py` (`view_sku`, `edit_sku`, `select_skus_to_merge`, `configure_merge`, `execute_merge`, `get_merge_preview`)

- **Product inventory routes retained direct SKU/lot lookups and route-level session control**
  - **Closed by:** moving SKU-by-inventory/code/id lookups, fresh/expired lot listing, quantity summation, and commit/rollback helpers into `app/services/product_inventory_route_service.py`.
  - **Routes affected:** `app/blueprints/products/product_inventory_routes.py` (`adjust_sku_inventory`, `get_sku_fifo_status`, `dispose_expired_sku`, `process_sale_webhook`, `process_return_webhook`, `create_manual_reservation`, `add_inventory_from_batch`)

- **Recipe form-parsing route-adjacent query/session access**
  - **Closed by:** moving portion-unit lookup/create, global-item lookup, org inventory lookup-by-global/name, and ownership-link flush/rollback handling into `app/services/recipe_form_parsing_service.py`.
  - **Routes affected:** `app/blueprints/recipes/form_parsing.py` (`ensure_portion_unit`, `extract_ingredients_from_form`)

- **Recipe create-routes query/rollback access remained route-local**
  - **Closed by:** moving purchased-recipe anti-plagiarism query, newly-created inventory item name lookup, category lookup-by-name, import recipe lookup, and rollback handling into `app/services/recipe_create_view_service.py`.
  - **Routes affected:** `app/blueprints/recipes/views/create_routes.py` (`_enforce_anti_plagiarism`, `new_recipe`, `clone_recipe`, `import_recipe`)

- **Recipe-library route-local ORM access (public list/detail/org marketplace)**
  - **Closed by:** moving public recipe listing/detail/org-marketplace queries and rollup aggregation into `app/services/recipe_library_view_service.py`.
  - **Routes affected:** `app/blueprints/recipe_library/routes.py` (`recipe_library`, `recipe_library_detail`, `organization_marketplace`, `_fetch_cost_rollups`)

- **Global-library detail/save/stats route-local ORM access**
  - **Closed by:** moving active-item/detail lookups, related-item retrieval, org inventory link lookup, and stats-item retrieval behind `app/services/global_library_view_service.py`.
  - **Routes affected:** `app/blueprints/global_library/routes.py` (`global_item_detail`, `save_global_item_to_inventory`, `global_library_item_stats`)

- **Public API global search + units route-adjacent query access**
  - **Closed by:** extracting public units lookup and global-item search query/payload shaping into `app/services/public_catalog_service.py`.
  - **Routes affected:** `app/blueprints/api/public.py` (`public_units`, `public_global_item_search`)

- **Dashboard route direct org/batch query access**
  - **Closed by:** moving selected-organization existence checks, active in-progress batch lookup, and rollback helpers into `app/services/app_dashboard_service.py`.
  - **Routes affected:** `app/blueprints/dashboard/routes.py` (`dashboard`)

- **Global-link and container-mismatch drawer direct route ORM access**
  - **Closed by:** moving global-item lookup/linking mutations and recipe/container lookup + yield persistence into dedicated drawer services.
  - **Routes affected:** `app/blueprints/api/drawers/drawer_actions/global_link.py`, `app/blueprints/api/drawers/drawer_actions/container_unit_mismatch.py`

- **Production-planning debug container endpoint route-local ORM access**
  - **Closed by:** moving recipe/container-category/container-list retrieval and shaping into `app/services/production_planning_debug_service.py`.
  - **Routes affected:** `app/blueprints/production_planning/routes.py` (`debug_recipe_containers`)

- **Expiration life/debug endpoint route-local ORM access**
  - **Closed by:** moving scoped history lookup and debug expiration query/shaping into `ExpirationService`.
  - **Routes affected:** `app/blueprints/expiration/routes.py` (`api_life_remaining`, `api_debug_expiration`)

- **Auth/onboarding route persistence in controllers**
  - **Closed by:** extracting verification/reset/onboarding token and profile persistence from routes to `app/services/auth_account_service.py`
  - **Routes affected:** `app/blueprints/auth/verification_routes.py`, `app/blueprints/auth/password_routes.py`, `app/blueprints/onboarding/routes.py`

- **Developer user/org route direct ORM access**
  - **Closed by:** moving user/organization lookups and org-user pagination to service boundaries.
  - **Routes affected:** `app/blueprints/developer/views/user_routes.py`, `app/blueprints/developer/views/organization_routes.py`

- **Start-batch route direct recipe lookup**
  - **Closed by:** moving recipe resolution to `app/services/batch_start_service.py`.
  - **Routes affected:** `app/blueprints/batches/start_batch.py`

- **Developer dashboard/masquerade direct ORM access**
  - **Closed by:** moving feature-flag state map and masquerade organization resolution behind developer services.
  - **Routes affected:** `app/blueprints/developer/views/dashboard_routes.py`, `app/blueprints/developer/views/masquerade_routes.py`

- **Drawer retention/unit-mapping direct route ORM access**
  - **Closed by:** moving org resolution and custom-unit mapping upsert to drawer service boundaries.
  - **Routes affected:** `app/blueprints/api/drawers/drawer_actions/retention.py`, `app/blueprints/api/drawers/drawer_actions/conversion_unit_mapping.py`
