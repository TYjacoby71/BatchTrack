# Consolidated Backlog (Undone Items Only)

## Launch Blockers & Infrastructure
- Stand up production Stripe: complete business verification, finish product lookup key coverage (including storage add-ons), load live API keys, and implement failed-payment handling/grace periods in `BillingService`.
- Configure transactional email delivery (provider choice, API keys, DNS records) and wire payment failure alert emails before go-live.
- Provision production PostgreSQL + backups, load all required environment variables, and document a tested deployment pipeline to the custom domain with SSL.
- Enable monitoring/observability (Sentry or similar) plus user-friendly error pages to catch and communicate production failures.
- Close remaining security gaps required for launch: enforce password strength rules, failed-login lockouts, and consistent server-side input validation across forms.
- Execute the Day 1–3 Launch Runbook items (Stripe infra, DB/env setup, email auth flows, signup-to-payment test pass) as go/no-go prerequisites.

## Bugs & Stability
- Standardize API responses to JSON across all routes (e.g., recipes quick actions), add matching integration tests, and audit for remaining HTML redirects.
- Resolve service-layer violations so blueprints never hit models directly (inventory, recipes, admin routes, etc.).
- Convert the recipes quick-add form to AJAX to preserve state; ensure ingredient edit forms retain unit selections on reload.
- Improve container selection logic and validation during inventory adjustments, and add micro-transaction thresholds plus detailed unit-conversion failure messaging.
- Add the missing validation wrapper around inventory adjustment flows to prevent FIFO desync; finish expiration timestamp fixes for intermediate batches.
- Normalize permission checks to `has_permission(...)`, enforce cleaner blueprint/service separation, and move lingering business logic out of templates.
- Standardize error payloads/middleware and create branded error pages so users see consistent feedback instead of raw Flask errors.
- Execute the FIX_IMMEDIATE testing checklist: verify API responses, service authority, error copy clarity, and persisted form state.

## Inventory & Costing Enhancements
- Fill metadata gaps in `UnifiedInventoryHistory`/FIFO lots (vendor/source attribution) and keep `InventoryItem.cost_per_unit` current without spoilage skew.
- Expose real-time “true cost per unit,” exclude spoil/trash from averages, and surface spoilage metrics in UI/API (ingredient-level %, cost, monthly summaries).
- Upgrade inventory list UX: effective-cost & spoilage columns, highlight thresholds, explanatory tooltips, and smart reorder suggestions tied to usage + spoil data.
- Complete Inventory FIFO upgrade gaps: remove `Batch.remaining_quantity`, add purchase history and adjustment interfaces, show effective cost in UI, and QA mobile responsiveness.
- Build comprehensive testing/migration assets: multi-purchase/mixed-source/mixed-unit/cost-averaging/concurrency tests, migration/rollback/backups/data-integrity scripts, and dependent-service audit updates.

## Future Features & Growth
- Implement the full retention/cancellation flow: multi-step objection handling, account pause offers, exit survey, analytics tracking, compliant UX, supporting services (RetentionFlow/Offer/AccountPause/ChurnAnalytics), frontend components, and corresponding email automation plus A/B rollout.
- Finish custom unit mapping experience: fully functional `CustomUnitMapping` flows with user attribution, density prompts for cross-type conversions, recipe editor blocks on unmapped units, improved messaging/tooling, training content, and unit manager status badges.
- Complete Day 4–5 Launch Runbook deliverables: QA core flows (FIFO, recipes, batches, permissions), ship onboarding checklist/help center links, and schedule lifecycle email sequences (day 0/3/7).
- Day 6 polish tasks: implement login lockouts, wire analytics + cookie notices, publish legal links in-app, and run performance tuning on slow queries.
- Day 7 soft-launch rehearsal: run full production dry run, cross-browser/device sanity checks, backup/restore drill, and formal go/no-go review.

## Long-Term / Strategic Initiatives
- Author and execute the inventory data migration plan (backups, rollback, verification scripts) before moving legacy data into the FIFO system.
- Expand retention program analytics post-launch: retention KPIs, objection performance, offer optimization, predictive churn modeling, and automated win-back sequences.
- Future unit-mapping roadmap items: mapping templates, AI-assisted suggestions, and shared community mapping libraries for common custom units.
