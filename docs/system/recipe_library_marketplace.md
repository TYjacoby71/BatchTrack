# Recipe Library & Marketplace

## Overview

The public recipe library allows organizations to publish curated formulations to a shared marketplace. Each published recipe carries its product group, category skin, pricing mode (private/free/sale), optional Shopify URL, and moderation status. Developers can always preview the library; customers only see the link when `FEATURE_RECIPE_LIBRARY_NAV` is enabled.

## Feature Flags

| Flag | Description |
| --- | --- |
| `FEATURE_RECIPE_SHARING_CONTROLS` | Enables the private/public + free/sale controls on the recipe form along with image uploads. |
| `FEATURE_RECIPE_LIBRARY_NAV` | Shows the “Recipe Library” link in customer/public navigation. |
| `FEATURE_RECIPE_PURCHASE_OPTIONS` | Displays Shopify purchase buttons on public recipe cards and detail pages. |

## Submission Flow

1. Recipe editors toggle visibility (private vs. public) and sale mode (free vs. sale).
2. Marketplace metadata (product group, notes, public description, Shopify URL, cover image) flows through `RecipeMarketplaceService`.
3. `create_recipe` / `update_recipe` persist marketplace columns on the `Recipe` model.
4. Public pages only surface recipes meeting all gating rules (`is_public`, `marketplace_status == 'listed'`, and org not blocked).

## Moderation

* Organizations can be blocked globally via the new `recipe_library_blocked` flag.
* Individual recipes track `marketplace_blocked`, `marketplace_block_reason`, and `marketplace_violation_count`.
* Moderation actions are logged in `RecipeModerationEvent`.

## Statistics & Analytics

`AnalyticsDataService.get_recipe_library_metrics()` exposes:

- `total_public`: number of public recipes.
- `total_for_sale`: public recipes with sale pricing.
- `average_sale_price`: mean sale price across live listings.
- `average_yield_per_dollar`: average predicted yield divided by average cost per batch (from `RecipeStats`).
- `top_group_name` / `top_group_count`: leading product group.

These metrics feed the developer system statistics page and the public library hero cards.

## Navigation & Access

- Developers always see the library link in their dropdown.
- Customers/public visitors see the link when `FEATURE_RECIPE_LIBRARY_NAV` is enabled.
- Routes are whitelisted via `recipe_library_bp.recipe_library` and `recipe_library_bp.recipe_library_detail`.

## Templates, Components & How-To

- **`library/recipe_library.html`** – filterable grid that reuses `components/shared/stat_card.html` to highlight public totals, average batch costs, and top groups; each card shows the creator’s public description, blurred content notice, and optional Shopify CTA.
- **`library/recipe_detail.html`** – public detail surface that keeps instructions, ingredients, consumables, and packaging blurred for general visitors while exposing them for developers or impersonated orgs.
- **`components/shared/stat_card.html`** – shared macro so the library hero and developer System Statistics dashboard render KPIs consistently.

### How-to: publish a public or paid recipe

1. Open any recipe (or create a new one) and scroll to the **“Recipe Library & Marketplace”** section (available whenever `FEATURE_RECIPE_SHARING_CONTROLS` is enabled).
2. Toggle **Public** sharing, choose a **Recipe Collection Group**, and pick a **Listing Type** (Free vs For Sale). Provide a sale price and optional Shopify URL if charging to enable the CTA (`FEATURE_RECIPE_PURCHASE_OPTIONS`).
3. Write a customer-facing **Public Description** and upload a square cover image (PNG/JPG/GIF/WEBP). Use the “Remove existing image” button to clear an existing asset when needed.
4. Save or publish the recipe, then click the **Recipe Library** nav link (requires `FEATURE_RECIPE_LIBRARY_NAV`) to confirm the public card and detail view.

### Customer experience (current behavior)

1. Public visitors (or logged-in users without developer/impersonation rights) can browse library cards, read the public description, and see cost/yield stats.
2. Clicking a card opens the detail page. Because entitlement is not yet enforced, instructions/ingredients/consumables/packaging remain blurred with a call-to-action explaining the need to purchase or work with a developer.
3. Developers impersonating an org owner (or future entitled buyers) see full content unblurred.

## Future Enhancements

- Entitlement-aware detail view so purchased recipes display unblurred instructions/ingredients once billing hooks confirm access.
- Paid-content delivery (PDFs, SKU bundles, or asset downloads) triggered after Shopify checkout or future embedded purchase flows.
- Creator analytics and moderation tooling (sales/violation dashboards, status toggles, automated freeze/unfreeze actions) for support staff.
