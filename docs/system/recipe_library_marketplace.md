# Recipe Library & Marketplace

## Overview

The public recipe library allows organizations to publish curated formulations to a shared marketplace. Each published recipe carries its product group, category skin, pricing mode (private/free/sale), optional Shopify URL, and moderation status. Developers can always preview the library; customers only see the link when `FEATURE_RECIPE_LIBRARY_NAV` is enabled.

## Feature Flags

| Flag | Description |
| --- | --- |
| `FEATURE_RECIPE_SHARING_CONTROLS` | Enables the private/public + free/sale controls on the recipe form along with image uploads. |
| `FEATURE_RECIPE_LIBRARY_NAV` | Shows the “Recipe Library” link in customer/public navigation. |
| `FEATURE_RECIPE_PURCHASE_OPTIONS` | Displays Shopify purchase buttons on public recipe cards and detail pages. |
| `FEATURE_ORG_MARKETPLACE_DASHBOARD` | Enables the public-facing Organization Marketplace dashboard surface and related navigation links. |
| `FEATURE_RECIPE_MARKETPLACE_DISPLAY` | Controls recipe marketplace display visibility in navbar and public-facing areas. |

## Submission Flow

1. Recipe editors toggle visibility (private vs. public) and sale mode (free vs. sale).
2. Marketplace metadata (product group, notes, public description, Shopify URL, cover image) flows through `RecipeMarketplaceService`.
3. `create_recipe` / `update_recipe` persist marketplace columns on the `Recipe` model.
4. Public pages only surface recipes meeting all gating rules (`is_public`, `marketplace_status == 'listed'`, and org not blocked).

## Moderation

* Organizations can be blocked globally via the new `recipe_library_blocked` flag.
* Individual recipes track `marketplace_blocked`, `marketplace_block_reason`, and `marketplace_violation_count`.
* Moderation actions are logged in `RecipeModerationEvent`.

## Origin & Lineage

* Every recipe now tracks two perspectives of ownership:
  * **Global origin** (`root_recipe_id`) — the canonical ancestor shared across the entire platform (e.g., BatchTrack native recipes or the very first customer-authored record).
  * **Organization origin** (`org_origin_recipe_id` + `org_origin_type`) — the recipe that acts as the starting point for a specific organization’s tree. Purchased recipes become the origin for the buying org but retain a reference back to the selling org.
* Origin metadata captures whether a listing is `batchtrack_native`, `authored`, or `purchased` while also storing download/purchase counters for future analytics.
* A new internal route (`/recipes/<id>/lineage`) renders the “Recipe Lineage” page with:
  * A tree visualization of clones, parent/child variations, and event history.
  * Origin summary including purchased stamps, links back to the creator’s public listings, and quick navigation to the organization marketplace dashboard (feature-flagged).
* The customer view now surfaces origin badges (BatchTrack Native vs. Purchased Origin) plus estimated download/purchase counts so buyers understand where formulations came from.

## Statistics & Analytics

`AnalyticsDataService.get_recipe_library_metrics()` exposes:

- `total_public`: number of public recipes.
- `total_for_sale`: public recipes with sale pricing.
- `average_sale_price`: mean sale price across live listings.
- `average_yield_per_dollar`: average predicted yield divided by average cost per batch (from `RecipeStats`).
- `top_group_name` / `top_group_count`: leading product group.
- `batchtrack_native_count`: number of listings whose origin type is `batchtrack_native`.
- `total_downloads` / `total_purchases`: rollups of the new download/purchase counters stored per recipe (used in cards + organization marketplaces).

These metrics feed the developer system statistics page and the public library hero cards.

## Navigation & Access

- Developers always see the library link in their dropdown.
- Customers/public visitors see the link when `FEATURE_RECIPE_LIBRARY_NAV` is enabled.
- Routes are whitelisted via `recipe_library_bp.recipe_library` and `recipe_library_bp.recipe_library_detail`.
- The organization-specific marketplace surface lives at `/recipes/library/organizations/<org_id>` and is gated by `FEATURE_ORG_MARKETPLACE_DASHBOARD`. The public cards link to this view whenever the flag is enabled.
- Filter controls now include origin type, organization, rich search (token-based narrowing), and advanced sorting (newest/oldest/downloads/price).

## Templates, Components & How-To

- **`library/recipe_library.html`** – filterable grid that reuses `components/shared/stat_card.html` to highlight public totals, average batch costs, and top groups; each card shows the creator’s public description, blurred content notice, and optional Shopify CTA.
- **`library/recipe_detail.html`** – public detail surface that keeps instructions, ingredients, consumables, and packaging blurred for general visitors while exposing them for developers or impersonated orgs.
- **`components/shared/stat_card.html`** – shared macro so the library hero and developer System Statistics dashboard render KPIs consistently.
- **`library/organization_marketplace.html`** – feature-flagged organization dashboard listing all public recipes for a single org with summary stats (listings, downloads, purchases) and the same CTA set as the main library.
- **`pages/recipes/recipe_lineage.html`** – authenticated (internal) page showing the family tree, lineage events, and origin summary for any recipe.

### How-to: publish a public or paid recipe

1. Open any recipe (or create a new one) and scroll to the **“Recipe Library & Marketplace”** section (available whenever `FEATURE_RECIPE_SHARING_CONTROLS` is enabled).
2. Toggle **Public** sharing, choose a **Recipe Collection Group**, and pick a **Listing Type** (Free vs For Sale). Provide a sale price and optional Shopify URL if charging to enable the CTA (`FEATURE_RECIPE_PURCHASE_OPTIONS`).
3. Write a customer-facing **Public Description** and upload a square cover image (PNG/JPG/GIF/WEBP). Use the “Remove existing image” button to clear an existing asset when needed.
4. Save or publish the recipe, then click the **Recipe Library** nav link (requires `FEATURE_RECIPE_LIBRARY_NAV`) to confirm the public card and detail view.

### Customer experience (current behavior)

1. Public visitors (or logged-in users without developer/impersonation rights) can browse library cards, read the public description, and see cost/yield stats.
2. Clicking a card opens the detail page. Because entitlement is not yet enforced, instructions/ingredients/consumables/packaging remain blurred with a call-to-action explaining the need to purchase or work with a developer.
3. Developers impersonating an org owner (or future entitled buyers) see full content unblurred.

### How-to: inspect recipe lineage

1. Open any internal recipe detail page (`/recipes/<id>/view`) and select **View Lineage**.
2. Review the “Origin & Ownership” card to confirm whether the recipe is BatchTrack native, org-authored, or a purchased origin (with links back to the creator’s public listings).
3. Use the lineage tree to trace variations vs. clones. Hovering the badges highlights the path from the global origin to the currently selected recipe.
4. Consult the event timeline for actions such as `CLONE`, `VARIATION`, or `PROMOTE_TO_PARENT`.

### How-to: browse an organization marketplace

1. Enable `FEATURE_ORG_MARKETPLACE_DASHBOARD`, then select the **Marketplace** link shown beside each creator’s name in the public library.
2. Use the search, listing-type, and sorting controls to narrow to the listings you need. Stats update live (listings, downloads, purchases).
3. Cards reuse the same CTA/hiding rules as the main library. Purchase links are only shown when `FEATURE_RECIPE_PURCHASE_OPTIONS` is enabled.
4. Use the back link to return to the global view with the current filter state preserved.

## Future Enhancements

- Entitlement-aware detail view so purchased recipes display unblurred instructions/ingredients once billing hooks confirm access.
- Paid-content delivery (PDFs, SKU bundles, or asset downloads) triggered after Shopify checkout or future embedded purchase flows.
- Creator analytics and moderation tooling (sales/violation dashboards, status toggles, automated freeze/unfreeze actions) for support staff.
