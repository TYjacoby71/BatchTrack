# Launch Runbook (Founder Only)

Audience: Internal. Purpose: day-by-day schedule, owners, checklists, go/no-go, rollback.

Window: 10-14 days. Source of truth for blockers: [CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md).

## Roles
- Founder: decision maker, QA lead, comms
- Engineering: infra, auth, billing, monitoring
- Marketing: site, assets, emails, Product Hunt/social
- Support: help center, inbox/SLA

## Daily Plan

### Day 1 - Infra and Billing setup
- [ ] Stripe products (lookup keys) created and match subscription_tiers.json
- [ ] Stripe live keys and webhook endpoint configured
- [ ] Production database and env vars loaded; backups enabled
- [ ] Domain and SSL configured
- [ ] Error monitoring (Sentry or similar) wired

### Day 2 - Email and Auth
- [ ] Choose providers: Resend/Postmark (transactional), ConvertKit/Beehiiv (marketing)
- [ ] DNS: SPF, DKIM, DMARC (start with p=none)
- [ ] Email verification and password reset flows working
- [ ] Welcome emails templated

### Day 3 - Signup to Payment E2E
- [ ] Account creation -> email verify -> org creation
- [ ] Subscribe -> Stripe checkout -> webhook grants access
- [ ] Failed payment path and grace period
- [ ] Subscription tier enforcement

### Day 4 - Core flows QA
- [ ] Inventory FIFO and adjustments
- [ ] Recipe creation and portioning
- [ ] Start batch -> finish -> product creation
- [ ] Permissions and org isolation

### Day 5 - Onboarding and Help
- [ ] In-app onboarding checklist mirrors Getting Started
- [ ] Trigger day 0/3/7 emails on key events
- [ ] Help center linked from empty states
- [ ] Contact route and basic SLA

### Day 6 - Security and Polish
- [ ] Rate limits, lockouts, security headers
- [ ] Analytics script and cookie notice if required
- [ ] Legal pages in footer
- [ ] Performance pass (N+1, slow queries)

### Day 7 - Soft launch rehearsal
- [ ] Full dry run on production
- [ ] Multi-device/browser sanity
- [ ] Backup and restore test
- [ ] Go / No-Go review

## Go / No-Go Criteria
- Stripe live flow passes 3 consecutive end-to-end tests
- Email verification and password reset succeed reliably
- Batch finish creates products and COGS reliably
- Error rate < 1% on core endpoints in rehearsal
- No P0/P1 bugs open

## Rollback Plan
- Feature flags to disable signup/billing
- Roll back to last known good build
- Revoke Stripe webhook (pause events)
- Status update to waitlist; ETA for reopen

## Communications Plan
- Waitlist: announce 24h before, then live
- Social: queued thread and LinkedIn post
- Product Hunt (optional): day after stability confirmation
- Changelog: create entry at go-live

## Post-Launch (Week 1)
- Daily triage window (2 x 30 min)
- Review telemetry: signups, activation, failed payments
- Ship fixes and update changelog
- Expand help with top FAQs

## Notes
- Update sitemap/robots with real domain (marketing/public)
- Keep FUTURE_ROADMAP.md separate from launch scope