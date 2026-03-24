# Parallel Flags Tracker (Boundary Program)

Purpose: track non-blocking risks discovered while extracting blueprint boundary violations so adjacent hardening work can run in parallel.

## Open flags

1. **Auth token flow duplication across modules**
   - **Surface:** `app/services/signup_service.py`, `app/services/user_invite_service.py`, `app/services/auth_account_service.py`
   - **Flag:** verification/reset token field writes now exist in multiple services; this can drift unless a single token-lifecycle authority is adopted.
   - **Parallel action:** centralize token issuance/clear semantics in one service and migrate invite/signup writers to use it.
   - **Status:** open

2. **Public/global query boundaries still route-adjacent**
   - **Surface:** `app/blueprints/api/public.py`
   - **Flag:** heavy `GlobalItem` query and alias-table fallback logic remains inside route module.
   - **Parallel action:** extract search/query construction to a dedicated public catalog service with route-only transport logic.
   - **Status:** open

3. **Developer support submissions shaping remains route-local**
   - **Surface:** `app/blueprints/developer/views/organization_routes.py`
   - **Flag:** support submissions route still owns substantial grouping/selection shaping and should move behind a service boundary over time.
   - **Parallel action:** extract support-submissions grouping/selection pipeline into a dedicated developer support service.
   - **Status:** open

4. **Production-planning debug endpoint mixes diagnostics with data access**
   - **Surface:** `app/blueprints/production_planning/routes.py`
   - **Flag:** debug route performs direct `db.session` and scoped inventory/category queries.
   - **Parallel action:** move debug data fetch to production-planning debug service; keep route as response formatter.
   - **Status:** open

5. **Known integration posture still incomplete**
   - **Surface:** `app/services/whop_service.py`, `app/services/billing_service.py`, `app/services/pos_integration.py`, soap push UI flow
   - **Flag:** Whop and Soap push remain partial/stubbed, and POS production module still embeds mock/test classes.
   - **Parallel action:** execute Workstream C items from boundary report + consolidated backlog.
   - **Status:** open

## Recently closed flags

- **Global-link and container-mismatch drawer direct route ORM access**
  - **Closed by:** moving global-item lookup/linking mutations and recipe/container lookup + yield persistence into dedicated drawer services.
  - **Routes affected:** `app/blueprints/api/drawers/drawer_actions/global_link.py`, `app/blueprints/api/drawers/drawer_actions/container_unit_mismatch.py`

- **Production-planning debug container endpoint route-local ORM access**
  - **Closed by:** moving recipe/container-category/container-list retrieval and shaping into `app/services/production_planning_debug_service.py`.
  - **Routes affected:** `app/blueprints/production_planning/routes.py` (`debug_recipe_containers`)

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
