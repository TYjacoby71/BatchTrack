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

- **`library/recipe_library.html`** – customer-facing grid with filters and aggregated stats (public count, average batch cost, top creators). Cards surface the public description, cost breakdown, and optional Shopify CTA.
- **`library/recipe_detail.html`** – detail page for each public recipe. Standard visitors can see the hero, description, and cost stats while instructions/ingredients/consumables/packaging stay blurred. Developers impersonating an org (or future entitled buyers) see full details.
- **`components/shared/stat_card.html`** – shared macro used both by the library hero and the developer System Statistics dashboard to keep KPI blocks consistent.

### Publishing a public or paid recipe

1. Open the recipe (or create a new one) and scroll to the **“Recipe Library & Marketplace”** card (available whenever `FEATURE_RECIPE_SHARING_CONTROLS` is enabled).
2. Toggle **Public** sharing, select a **Collection Group**, and pick a **Listing Type** (Free or For Sale). Provide a sale price/Shopify link if you’re charging.
3. Write a customer-facing **Public Description** and upload a square cover image (PNG/JPG/GIF/WEBP). Use the “Remove” button to clear an existing cover.
4. Click **Save** or **Publish**, then verify the public experience via the **Recipe Library** navigation entry (requires `FEATURE_RECIPE_LIBRARY_NAV`) and ensure purchase toggles behave as expected (`FEATURE_RECIPE_PURCHASE_OPTIONS`).
