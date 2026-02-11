# 2026-02-10 — Pricing Page Launch, Public CTA Routing, and Header Offset Fix

## Summary
- Added a dedicated public `/pricing` sales page with a maker-first layout and side-by-side tier comparison.
- Updated public pricing links/buttons to route users to `/pricing` instead of unresolved anchors.
- Updated free-trial CTAs to go directly to `/auth/signup`.
- Removed homepage development/waitlist gating surfaces from the public signup path.
- Fixed public-header layout drift by removing conflicting global navbar/body spacing CSS.

## Problems Solved
- Pricing links on public pages pointed to `#pricing` anchors that did not resolve consistently across routes.
- Trial CTAs were routed through a development modal/waitlist detour instead of direct signup.
- Footer and bottom links included placeholder targets instead of stable destinations.
- Public pages with redirects could render with the header shifted down due to conflicting global CSS.

## Key Changes
- `app/routes/pricing_routes.py`
  - Added dedicated public `/pricing` route handler with maker-first metadata context (`page_title`, `page_description`, `canonical_url`, `page_og_image`).
- `app/services/public_pricing_page_service.py`
  - Added pricing context builder for tier cards, lifetime-offer-first display, and comparison rows.
- `app/templates/pages/public/pricing.html`
  - New dedicated pricing/sales page with:
    - Lifetime launch cards shown first when seats remain.
    - Three primary tiers (Hobbyist, Enthusiast, Fanatic).
    - Column-style checkbox comparison table.
    - Direct CTA links into signup flows.
- `app/templates/homepage.html`
  - Rewired nav/footer pricing links to `/pricing`.
  - Rewired free-trial CTAs to `/auth/signup`.
  - Removed development banner/modal + waitlist modal chain.
  - Replaced placeholder footer links with concrete internal destinations.
- `app/templates/layout.html`
  - Public header pricing nav now points to `/pricing`.
  - Added default OG/Twitter image fallback for pages that do not pass `page_og_image`.
- `app/route_access.py`
  - Added `/pricing` endpoint + path to public route allow-list.
- `app/static/style.css`
  - Removed navbar `position: relative` override that conflicted with `fixed-top`.
  - Removed global `body` top padding that caused public header offset drift.
- `app/static/images/og/batchtrack-default-og.svg`
  - Added app-wide social preview fallback image.
- `app/static/images/og/batchtrack-pricing-og.svg`
  - Added pricing-specific social preview image.

## Impact
- Public acquisition flow is cleaner: homepage → pricing → signup.
- Pricing discovery and conversion paths are more consistent and deterministic.
- Public-header pages retain stable top alignment after redirects and route transitions.
- Metadata for edited public route/template surfaces follows maker-first SEO guidance.

## Files Modified
- `app/__init__.py`
- `app/blueprints_registry.py`
- `app/routes/pricing_routes.py`
- `app/services/public_pricing_page_service.py`
- `app/route_access.py`
- `app/static/style.css`
- `app/templates/homepage.html`
- `app/templates/layout.html`
- `app/templates/pages/public/pricing.html`
- `docs/system/APP_DICTIONARY.md`
- `docs/system/SEO_GUIDE.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-10-pricing-page-and-public-cta-flow.md` (this file)
