# Free Tier Gating

This document enumerates gated actions, prompts, and upgrade paths for Free tier users.

## Gated actions
- Inventory adjustments: requires `inventory.adjust`
- Batch start: requires `batches.create`
- Other write actions inherit permission checks in their views/services

## Prompts/CTAs
- Inventory screens show an upgrade CTA in the header area when the user lacks `inventory.adjust`.
- Recipe form shows an upgrade CTA for starting batches when lacking `batches.create`.
- Billing upgrade page: `/billing/upgrade`.

## Behavior
- Anonymous users can access `/tools` and `/exports/tool/*`.
- Recipe exports require authentication and org scope.
