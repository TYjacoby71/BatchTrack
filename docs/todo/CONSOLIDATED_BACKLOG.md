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

## Test Suite Hygiene Backlog
- Run a relevance pass on older tests (especially files last touched before `2026-01-01`) and either update assertions to current service contracts or retire obsolete cases.
- Consolidate overlapping canonicalization coverage (`inventory`, `expiration`, `POS`, `reservation`) so behavior is tested once at the right service boundary with thin route smoke tests.
- Reduce broad permission bypass usage (`SKIP_PERMISSIONS=True`) in integration tests by defaulting to authenticated fixtures and using bypass only when explicitly required by scenario.
- Add lightweight test taxonomy markers (for example `@pytest.mark.inventory`, `@pytest.mark.billing`, `@pytest.mark.auth`) to support selective CI execution and ownership reviews.
- Add a quarterly duplicate-name and duplicate-intent audit to catch drift early and keep test naming/intent unique across files.

## Future Features & Growth
- Ship the multi-step retention/cancellation experience end-to-end: retention landing page, objection-specific paths, exit survey, analytics, FTC-compliant cancellation, win-back emails, and phased rollout.
- Finish custom unit mapping experience: `CustomUnitMapping` flows with user attribution, density prompts, recipe editor enforcement, training content, and status badges in Unit Manager.
- Batch augmentation system: split base yield into scented/colored variations pre-finish, with percentage allocation, automatic sub-labels (101A-Lavender, 101B-Rose), added-ingredient tracking, and container redistribution.
- Recipe-bound instruction propagation + maker tool: duplicate instructions across every test and variation while preserving the exact source recipe ID linkage, and add a maker tool on the batch in-progress page so makers can pull up the linked instructions instantly.
- Multi-batch scheduling and resource optimization: plan batches across time with equipment scheduling and conflict prevention.
- Quality control integration: batch testing protocols, specification compliance, recall management, and certificate generation.
- Cost tracking and trend analysis: historical ingredient pricing, profit margin monitoring, recipe cost trends, and batch profitability (actual vs planned).
- Advanced reporting dashboard: cost optimization reports, inventory turn analysis, production efficiency metrics, supplier performance, and site analytics service integration.
- Maker-to-maker community platform: recipe sharing with ratings, ingredient marketplace, process documentation, collaboration tools, and maker profiles.
- Batchley AI assistant: conversational interface for production workflows, multi-modal input (voice, camera, file imports), smart purchase management via OCR, recipe/ingredient creation by voice/text, and contextual recommendations.
- API platform development: GraphQL API, webhook system for customers, auto-generated OpenAPI docs, and SDK generation.

## Long-Term / Strategic Initiatives
- Author and execute the inventory data migration plan (backups, rollback, verification scripts) before moving legacy data into the FIFO system.
- Expand retention program analytics post-launch: retention KPIs, objection performance, offer optimization, predictive churn modeling, and automated win-back sequences.
- Future unit-mapping roadmap items: mapping templates, AI-assisted suggestions, and shared community mapping libraries for common custom units.
- Complete static asset pipeline hardening: JS bundling + hashed manifest resolution is now in place for template-referenced entrypoints with legacy `app/static/js/**/*.min.js` removed. Remaining work is CSS bundling, CI enforcement (`npm ci && npm run build:assets`), and immutable cache-header rollout.
- Multi-region support: geographic distribution, local compliance, multi-currency, and language localization.
- Enterprise features: event sourcing, CQRS, service mesh, and enhanced multi-tenant isolation.
- Integration ecosystem: ERP (QuickBooks, Xero), e-commerce (Shopify, WooCommerce), shipping (FedEx, UPS), and compliance tools.
- Mobile and IoT: production floor app, barcode/QR scanning, mobile timers, smart scales, temperature monitoring, and environmental sensors.
- UI customization and accessibility: custom color schemes per org, high contrast mode, compact/spacious layouts, WCAG 2.1 AA compliance, screen reader optimization, keyboard navigation, and font size controls.
