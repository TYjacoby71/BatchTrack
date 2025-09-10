# Master QA & Launch Checklists

A single, consolidated source for all launch and QA checklists. Each section links back to its detailed reference document.

- Source docs:
  - LAUNCH: [docs/CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md), [docs/LAUNCH_RUNBOOK.md](LAUNCH_RUNBOOK.md)
  - QA: [docs/UNIT_MAPPING_QA.md](UNIT_MAPPING_QA.md), [docs/INVENTORY_COST_QA.md](INVENTORY_COST_QA.md), [docs/INVENTORY_UPGRADE_QA.md](INVENTORY_UPGRADE_QA.md), [docs/RETENTION_CANCELLATION_QA.md](RETENTION_CANCELLATION_QA.md)

---

## 1) Launch Checklists

### 1.1 Critical Pre-Launch Requirements

(From CRITICAL_PRELAUNCH.md)

#### 🔐 STRIPE INTEGRATION (CRITICAL)
- [ ] Stripe Account Setup: Business verification complete
- [ ] Products Created: All tiers with exact lookup keys
- [ ] API Keys: Live keys in production secrets
- [ ] Webhook Endpoint: Configured and tested
- [ ] Payment Flow: End-to-end signup to payment tested
- [ ] Failed Payment Handling: Graceful error recovery

#### 📧 EMAIL SYSTEM (CRITICAL)
- [ ] Email Service: SendGrid/AWS SES configured
- [ ] Email Verification: Working signup verification flow
- [ ] Password Reset: Functional reset system
- [ ] Welcome Emails: New user onboarding flow
- [ ] Payment Alerts: Failed payment notifications

#### 🏗️ PRODUCTION INFRASTRUCTURE (CRITICAL)
- [ ] Database: PostgreSQL configured and migrated
- [ ] Domain: Custom domain with SSL certificate
- [ ] Environment Variables: All secrets properly set
- [ ] Deployment: Production deployment tested
- [ ] Monitoring: Basic error tracking (Sentry/similar)

#### 🔒 SECURITY HARDENING (HIGH PRIORITY)
- [ ] Rate Limiting: Auth endpoints protected
- [ ] Security Headers: HTTPS, CSRF, XSS protection
- [ ] Password Requirements: Strength validation
- [ ] Account Lockout: Failed login protection
- [ ] Input Validation: All forms sanitized

#### ⚖️ LEGAL COMPLIANCE (CRITICAL)
- [ ] Terms of Service: Published and linked
- [ ] Privacy Policy: GDPR/privacy compliant
- [ ] Cookie Policy: If using analytics
- [ ] Billing Terms: Subscription terms clear

#### 🧪 CORE FUNCTIONALITY VALIDATION (HIGH PRIORITY)
- [ ] Signup Flow: Complete organization creation
- [ ] FIFO System: Inventory deduction working
- [ ] Batch Production: End-to-end batch workflow
- [ ] Multi-tenant: Organization data isolation
- [ ] Subscription Tiers: Feature enforcement working
- [ ] Permission System: Role-based access control

#### 📊 ERROR HANDLING (HIGH PRIORITY)
- [ ] API Consistency: Standardized response formats
- [ ] Error Pages: User-friendly error messages
- [ ] Logging System: Application error tracking
- [ ] Service Authority: No service layer bypassing
- [ ] Organization Scoping: Data isolation verified

#### 🎯 LAUNCH READINESS (PHASES)
- [ ] Phase 1: Infra (Stripe, DB/env, email, SSL)
- [ ] Phase 2: Integration testing (signup→payment, core workflows, isolation, monitoring)
- [ ] Phase 3: Security & polish (hardening, legal pages, error scenarios)
- [ ] Phase 4: Final validation (E2E, multi-device, perf/load, support)

---

### 1.2 Launch Runbook – Daily Plan (Days 1–7)

(From LAUNCH_RUNBOOK.md)

#### Day 1 – Infra and Billing setup
- [ ] Stripe products (lookup keys) created and match subscription_tiers.json
- [ ] Stripe live keys and webhook endpoint configured
- [ ] Production database and env vars loaded; backups enabled
- [ ] Domain and SSL configured
- [ ] Error monitoring (Sentry or similar) wired

#### Day 2 – Email and Auth
- [ ] Choose providers: Resend/Postmark (transactional), ConvertKit/Beehiiv (marketing)
- [ ] DNS: SPF, DKIM, DMARC (start with p=none)
- [ ] Email verification and password reset flows working
- [ ] Welcome emails templated

#### Day 3 – Signup to Payment E2E
- [ ] Account creation → email verify → org creation
- [ ] Subscribe → Stripe checkout → webhook grants access
- [ ] Failed payment path and grace period
- [ ] Subscription tier enforcement

#### Day 4 – Core flows QA
- [ ] Inventory FIFO and adjustments
- [ ] Recipe creation and portioning
- [ ] Start batch → finish → product creation
- [ ] Permissions and org isolation

#### Day 5 – Onboarding and Help
- [ ] In-app onboarding checklist mirrors Getting Started
- [ ] Trigger day 0/3/7 emails on key events
- [ ] Help center linked from empty states
- [ ] Contact route and basic SLA

#### Day 6 – Security and Polish
- [ ] Rate limits, lockouts, security headers
- [ ] Analytics script and cookie notice if required
- [ ] Legal pages in footer
- [ ] Performance pass (N+1, slow queries)

#### Day 7 – Soft launch rehearsal
- [ ] Full dry run on production
- [ ] Multi-device/browser sanity
- [ ] Backup and restore test
- [ ] Go / No-Go review

#### Go / No-Go Criteria
- [ ] Stripe live flow passes 3 consecutive end-to-end tests
- [ ] Email verification and password reset succeed reliably
- [ ] Batch finish creates products and COGS reliably
- [ ] Error rate < 1% on core endpoints in rehearsal
- [ ] No P0/P1 bugs open

#### Rollback Plan
- [ ] Feature flags to disable signup/billing
- [ ] Roll back to last known good build
- [ ] Revoke Stripe webhook (pause events)
- [ ] Status update to waitlist; ETA for reopen

#### Communications Plan
- [ ] Waitlist: announce 24h before, then live
- [ ] Social: queued thread and LinkedIn post
- [ ] Product Hunt (optional): day after stability confirmation
- [ ] Changelog: create entry at go-live

#### Post-Launch (Week 1)
- [ ] Daily triage window (2 x 30 min)
- [ ] Review telemetry: signups, activation, failed payments
- [ ] Ship fixes and update changelog
- [ ] Expand help with top FAQs

---

## 2) Product QA Checklists

### 2.1 Custom Unit & Mapping – Launch Checklist

(From UNIT_MAPPING_QA.md)

- [ ] `Unit` table has `is_custom` and `is_mapped` flags
- [ ] `CustomUnitMapping` fully functional with user_id support
- [ ] Density assignment via mapping prompt (optional)
- [ ] Recipe editor blocks unmapped units
- [ ] Stock check blocks:
  - [ ] Unmapped units
  - [ ] Cross-type units without density
- [ ] Mapping form includes training and validation
- [ ] Messaging clean and non-technical
- [ ] Custom units clearly labeled in UI

### 2.2 Inventory Cost Tracking – QA Checklist

(From INVENTORY_COST_QA.md)

#### Core Data Structure
- [ ] Inventory history logs all changes with `change_type`, `quantity_change`, `unit_cost`, `timestamp`, `source`
- [ ] Supports `used_for_batch_id` traceability
- [ ] InventoryItem `quantity` reflects stock; `cost_per_unit` reflects last purchase; supports `low_stock_threshold`

#### Cost Calculations
- [ ] True cost per unit = total_purchase_cost / (units_used + units_remaining)
- [ ] Exclude spoiled/trash from denominator; compute dynamically (do not store)
- [ ] Spoilage metrics: % lost, total spoilage cost, monthly summary

#### Inventory Display
- [ ] List view shows Effective Cost and Spoiled This Month
- [ ] Highlight thresholds (10–20% yellow, >20% red)
- [ ] Tooltips show loss and spoilage details; reorder suggestions auto-generated

### 2.3 Inventory FIFO Upgrade – QA Checklist

(From INVENTORY_UPGRADE_QA.md)

#### Database Structure
- [ ] InventoryHistory table with id, inventory_item_id, change_type, quantity, unit, timestamps, source, cost fields; FKs verified

#### Raw Ingredient FIFO
- [ ] Purchase event tracking with vendor/source and cost per purchase
- [ ] FIFO deduction logic with multi-purchase scenarios; unit consistency verified

#### Intermediate Ingredient FIFO
- [ ] Remove `remaining_quantity` from Batch
- [ ] Batch completion creates inventory records
- [ ] FIFO deduction from batches; mixed-source deductions tested; traceability verified

#### UI/UX Implementation
- [ ] Purchase history view; inventory adjustment UI; FIFO transaction log; cost tracking display; low stock alerts; mobile responsive

#### Integration Points
- [ ] Update stock check; modify batch deduction; update adjustment routes; integrate unit conversion; test recipe scaling impact

#### Migration Process
- [ ] Data migration plan; backups; rollback test; data integrity verified; dependent services updated

#### Testing Scenarios
- [ ] Multi-batch deduction; mixed unit conversions; cost averaging; concurrent transactions; edge cases

### 2.4 Retention & Cancellation Flow – QA Checklist

(From RETENTION_CANCELLATION_QA.md)

#### Cancellation Flow Requirements
- [ ] Redirect to retention landing; track intent; keep session; log timestamp
- [ ] Landing page elements: video, value reminder, social proof, 4 objection buttons

#### Objection Handling Pages
- [ ] Cost concerns page: discount, downgrade, payment plan, ROI calculator, accept/continue buttons
- [ ] Not making money page: success stories, consultation offer, extended trial, resources, get help/continue buttons
- [ ] Taking a break page: pause options, data preservation, reactivation reminders, pause/continue buttons
- [ ] Alternative solution page: comparison chart, migration help, feature preview, stay/continue buttons

#### Final Confirmation & Exit Survey
- [ ] Final confirm page with three options (Pause, Back to Account, Cancel Completely)
- [ ] Exit survey with reason, suggestions, contact permission, final confirm

#### UX, Tracking, Compliance
- [ ] Navigation rules observed; progress indicators; mobile responsive; no back button traps
- [ ] Track selected objections, offers, time-on-page, final reason; store results
- [ ] Compliance: easy cancellation, ≤4 steps, clear Cancel Now, immediate confirmation
- [ ] User rights: access until period end; data export; refund policy; unsubscribe

---

## Notes
- Use this file during planning and QA. For details and rationale, follow the links to the source documents.