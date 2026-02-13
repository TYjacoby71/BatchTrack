# Consolidated Backlog (Undone Items Only)

## Launch Blockers & Infrastructure
- Stand up production Stripe: complete business verification, finish product lookup key coverage (including storage add-ons), load live API keys, and implement failed-payment handling/grace periods in `BillingService`.
- Configure transactional email delivery (provider choice, API keys, DNS records) and wire payment failure alert emails before go-live.
- Provision production PostgreSQL + backups, load all required environment variables, and document a tested deployment pipeline to the custom domain with SSL.
- Enable monitoring/observability (Sentry or similar) plus user-friendly error pages to catch and communicate production failures.
- Close remaining security gaps required for launch: enforce password strength rules, failed-login lockouts, and consistent server-side input validation across forms.
- Publish counsel-reviewed billing terms in-app and confirm footer/legal links are wired before analytics tracking begins.

## Launch Runbook Execution
- **Day 1 (Infra + Billing):** Create Stripe products with final lookup keys, load live keys + webhook, provision production database/backups, configure domain + SSL, and wire error monitoring.
- **Day 2 (Email + Auth):** Select transactional + marketing email providers, finish SPF/DKIM/DMARC, verify email verification/password reset/welcome flows end-to-end.
- **Day 3 (Signup→Payment E2E):** Run signup → email verify → org creation → paid checkout flow, ensure webhooks grant access, cover failed payment paths and tier enforcement.
- **Day 4 (Core Flow QA):** QA inventory FIFO + adjustments, recipe creation/portioning, batch start/finish/product creation, and permission/org isolation.
- **Day 5 (Onboarding + Help):** Build in-app onboarding checklist, hook empty states to help center/contact routes, and schedule lifecycle emails (day 0/3/7 triggers).
- **Day 6 (Security + Polish):** Finalize rate limits + lockouts + headers, enable analytics with cookie notice, publish legal links, and performance-test slow queries.
- **Day 7 (Soft Launch Rehearsal):** Execute full prod dry run, multi-device/browser checks, backup + restore test, and formal go/no-go review.

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
- Ship the multi-step retention/cancellation experience end-to-end: redirect from billing to a retention landing page (video/value props/testimonials), present four objection-specific paths (discount/downgrade, ROI/training, pause/reactivation reminders, migration help), gate final cancellation behind warnings + alternate actions, capture exit survey responses, and persist all analytics (intent events, offers shown/accepted, time-on-step). Ensure FTC-compliant easy cancellation, data export options, follow-up win-back emails, and phased rollout (A/B test → optimization → 100% launch) backed by RetentionFlow/Offer/AccountPause/ChurnAnalytics services and dedicated frontend components.
- Finish custom unit mapping experience: fully functional `CustomUnitMapping` flows with user attribution, density prompts for cross-type conversions, recipe editor enforcement against unmapped units, mapping-form training content/video guidance, clearer messaging, and status badges inside Unit Manager so users know which units are unmapped or pending density.

## Long-Term / Strategic Initiatives
- Author and execute the inventory data migration plan (backups, rollback, verification scripts) before moving legacy data into the FIFO system.
- Expand retention program analytics post-launch: retention KPIs, objection performance, offer optimization, predictive churn modeling, and automated win-back sequences.
- Future unit-mapping roadmap items: mapping templates, AI-assisted suggestions, and shared community mapping libraries for common custom units.
- Complete static asset pipeline hardening: JS bundling + hashed manifest resolution is now in place for template-referenced entrypoints with legacy `app/static/js/**/*.min.js` removed. Remaining work is CSS bundling, CI enforcement (`npm ci && npm run build:assets`), and immutable cache-header rollout.
