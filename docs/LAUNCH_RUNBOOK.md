# Launch Runbook (Founder Only)

Audience: Internal. Purpose: day-by-day schedule, owners, checklists, go/no-go, rollback.

Window: 10-14 days. Source of truth for blockers: docs/CRITICAL_PRELAUNCH.md.

## Roles
- Founder: decision maker, QA lead, comms
- Engineering: infra, auth, billing, monitoring
- Marketing: site, assets, emails, Product Hunt/social
- Support: help center, inbox/SLA

## Daily Plan

Each day references the canonical checklist items in [CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md). Do not maintain checklists here.

### Day 1 - Infra and Billing setup
- See: STRIPE INTEGRATION, PRODUCTION INFRASTRUCTURE

### Day 2 - Email and Auth
- See: EMAIL SYSTEM, SECURITY HARDENING (auth hardening)

### Day 3 - Signup to Payment E2E
- See: STRIPE INTEGRATION, CORE FUNCTIONALITY VALIDATION (subscription, permissions)

### Day 4 - Core flows QA
- See: CORE FUNCTIONALITY VALIDATION

### Day 5 - Onboarding and Help
- See: LEGAL COMPLIANCE (policies) and relevant product docs

### Day 6 - Security and Polish
- See: SECURITY HARDENING, ERROR HANDLING

### Day 7 - Soft launch rehearsal
- See: LAUNCH READINESS (Phase 4: Final Validation) in CRITICAL_PRELAUNCH.md

## Go / No-Go
- Use the criteria in [CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md) under LAUNCH READINESS and BLOCKERS status.

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