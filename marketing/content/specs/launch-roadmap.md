# BatchTrack Launch Roadmap (Definitive)

Status: draft
Owner: Founder
Target window: 10–14 days to go-live (based on CRITICAL_PRELAUNCH.md)

## Goals
- Public site live with clear messaging and waitlist
- Production app live with billing, signups, and onboarding
- Legal, help, and support in place

## Workstreams

### 1) Marketing Site
- Content: landing, features, about (done)
- Docs/help: getting started + 4 core concepts (done)
- Legal: privacy, terms (done; review by counsel)
- Changelog page: create and link in footer
- SEO: robots.txt, sitemap.xml, title/description/OG
- Analytics: Plausible/GA4
- Waitlist form: connect to ConvertKit/Beehiiv with fields: email, maker type, Shopify (Y/N)

Owner: Marketing
Deadline: Day 3

### 2) Billing & Plans
- Stripe: products/lookup keys match `subscription_tiers.json`
- Live keys in prod env; webhook configured + verified
- Signup-to-payment happy path tested end-to-end
- Failed payment and grace period handling

Owner: Engineering
Deadline: Day 5

### 3) Signups & Auth
- Email verification in place (Resend/Postmark/SES)
- Password reset
- Org creation and role assignment
- Rate limits and lockouts

Owner: Engineering
Deadline: Day 5

### 4) Onboarding Flow
- In-app checklist mirrors Getting Started
- Trigger transactional emails (day 0/3/7)
- Link to docs/help from empty states
- Collect maker type + Shopify flag during onboarding

Owner: Product
Deadline: Day 6

### 5) Help & Support
- Help center linked in app and site
- Contact/support route and SLA
- Status page link (if available)

Owner: Support
Deadline: Day 6

### 6) Security & Monitoring
- Sentry (or similar) enabled
- Basic WAF/rate limiting
- Security headers and TLS
- Backups tested

Owner: Engineering
Deadline: Day 6

### 7) Launch Ops
- Email list warm-up plan
- Product Hunt draft + assets
- Social posts queued
- Founder availability for first 48 hours

Owner: Marketing
Deadline: Day 7

## Go-Live Checklist
- [ ] Domain + SSL for app and marketing
- [ ] Stripe live mode + webhook tested
- [ ] Email domain verified (SPF/DKIM/DMARC)
- [ ] Email verification + password reset
- [ ] Signup → billing → app access works
- [ ] Onboarding checklist present and functional
- [ ] Docs/help/legal linked in footer and app
- [ ] Error monitoring receiving events
- [ ] Backups scheduled and verified
- [ ] Robots.txt + sitemap.xml in place
- [ ] Analytics receiving events

## Post-Launch Day 1–7
- Review telemetry and signups daily
- Triage bugs within 24h
- Capture FAQs and expand help center
- Start changelog entries

## Notes
- See `/workspace/docs/todo/CRITICAL_PRELAUNCH.md` for blockers
- See `/workspace/docs/FUTURE_ROADMAP.md` for post-launch features
