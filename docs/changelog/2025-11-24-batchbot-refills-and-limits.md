# 2025-11-24 — BatchBot Refills & Usage Limits

## Summary
- Introduced separate **chat** vs **action** quotas for Batchley (BatchBot).
- Added a Stripe-powered **Batchley refill** add-on plus checkout flow.
- Public (unauthenticated) Batchley now stays free/unlimited; authenticated users see quota and refill messaging.
- BatchBot gains marketplace awareness to answer recipe marketplace questions.

## Problems Solved
- Customers could exhaust automation requests with no clear upgrade path.
- Support lacked visibility into the required Google AI keys and Batchley knobs.
- Batchley couldn’t answer marketplace-related questions.

## Key Changes
- `app/config.py`, `.env.example`: new env knobs `BATCHBOT_CHAT_MAX_MESSAGES`, `BATCHBOT_REFILL_LOOKUP_KEY`.
- `app/services/batchbot_usage_service.py`: tracks chat prompts separately, surfaces both buckets in quota responses.
- `app/services/batchbot_service.py`: exposes marketplace status tool + context, distinguishes chat vs job requests.
- `app/blueprints/api/routes.py`: limit responses include checkout URL for refill add-on.
- `app/services/billing_service.py`: handles standalone refill purchase webhooks via Stripe Checkout metadata.
- `app/seeders/addon_seeder.py`: seeds `batchbot_refill_100` add-on (100 action requests, one-time).
- `docs/changelog/CHANGELOG_INDEX.md`: linked this entry.

## Impact
- Users see “You’ve used all your BatchBot tokens” message plus a Stripe checkout link when either limit is hit.
- Batchley Q&A remains free on the public homepage while still respecting per-tier quotas when authenticated.
- Devs can locate every relevant env key (Google AI, chat cap, refill lookup key) via the Integrations checklist.
- Recipe marketplace questions route through the new `fetch_marketplace_status` tool.

## Files Modified
- `app/config.py`
- `.env.example`
- `app/seeders/addon_seeder.py`
- `app/services/batchbot_service.py`
- `app/services/batchbot_usage_service.py`
- `app/services/billing_service.py`
- `app/blueprints/api/routes.py`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2025-11-24-batchbot-refills-and-limits.md` (this file)

## Example: Refill Prompt API payload
```json
{
  "success": false,
  "error": "BatchBot request limit reached for the current window.",
  "limit": {
    "allowed": 100,
    "used": 100,
    "window_end": "2025-12-24T00:00:00+00:00"
  },
  "refill_checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```
