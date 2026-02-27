# SEO Surface Snapshot and Backlog

## Synopsis
This document records the current SEO-capable surface in BatchTrack and the active backlog for further search visibility improvements. It replaces older phased timeline assumptions with present-state implementation notes.

## Glossary
- **SEO surface**: Crawlable routes, metadata, structured data, and discoverable internal links.
- **Metadata context**: Route-provided values (`page_title`, `page_description`, `canonical_url`, OG fields) consumed by layout templates.
- **Library detail page**: Public global-item page (`/global-items/<id>-<slug>`) with canonical + JSON-LD context.

## Current Implementation State

### 1) Public crawlable pages
- Public endpoints include homepage/auth/legal/pricing/tools/help/library routes.
- Global library list and detail routes are public when feature-enabled.
- Tool exports and public API surfaces are publicly reachable by policy config.

### 2) Metadata pipeline
- Layout accepts route context for title/description/canonical/OG/Twitter tags.
- Public routes can provide page-level metadata for SEO/social previews.
- Default OG image fallback is wired when page-specific image is absent.

### 3) Global library SEO primitives
- Library index: `/global-items`
- Detail: `/global-items/<id>-<slug>` (canonical redirect enforcement)
- Detail pages set page title/description/canonical and include JSON-LD `Product` structured data.
- Detail pages expose related items and stats-backed context.

### 4) Robots/sitemap endpoints
- Public routing includes sitemap/robots/llms endpoints for crawler discovery and indexing controls.

## Active Backlog (Current)
- Broaden structured data coverage beyond global item details (for example FAQ/HowTo where appropriate).
- Expand maker-first metadata coverage for additional public pages and tools.
- Tighten internal linking paths between tools, library, and educational/help surfaces.
- Continue metadata enrichment for global items via curated `metadata_json` fields.

## Governance
- Use `docs/system/SEO_GUIDE.md` as the canonical implementation style guide for metadata copy/tone.
- Treat this file as state + backlog tracking, not an immutable rollout plan.

## Relevance Check (2026-02-17)
Validated against:
- `app/blueprints/global_library/routes.py`
- `app/route_access.py`
- `app/templates/layout.html`
- `app/templates/library/global_items_list.html`
- `app/templates/library/global_item_detail.html`
- `docs/system/SEO_GUIDE.md`
