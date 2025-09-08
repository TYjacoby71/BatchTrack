# Whop Integration — Planning Spec (Draft)

Owner: Product
Scope: Post-launch planning only (no build yet)

## Goals
- Link BatchTrack account to Whop account
- Publish a recipe from BatchTrack to a Whop product
- Receive sales webhooks to inform production planning

## Flows

### 1) Account Linking
- User clicks "Connect Whop" in Integrations
- OAuth or API token exchange; store tokens securely
- Scopes: read/write products, read orders, webhooks

### 2) Publish Recipe → Whop Product
- Choose recipe version and visibility
- Map BatchTrack fields → Whop product fields (title, description, media, attributes)
- Optional price and availability
- Create/update product on Whop

### 3) Webhooks
- Order created/updated
- Refunds/cancellations
- Inventory/product updates
- Security: HMAC signatures, replay protection, idempotency

## Data Model (minimal)
- whop_accounts: org_id, access_token, scopes, status
- whop_product_links: org_id, recipe_id, recipe_version, whop_product_id, status
- whop_webhook_events: id, org_id, type, payload, received_at, processed_at

## Rate Limits & Errors
- Respect Whop rate limits; exponential backoff
- Idempotent upserts for product sync
- Circuit-breaker on repeated failures

## Security
- Encrypt tokens at rest
- Signed webhook verification
- Principle of least privilege scopes

## Open Questions
- Pricing strategy and tiers on Whop
- How to represent variations/augmentations
- Export format for recipe (MD/JSON)
