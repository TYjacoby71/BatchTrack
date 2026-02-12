# 2026-02-12 — Homepage Brand Logo and Favicon Integration

## Summary
- Applied the uploaded square app tile as the browser/tab icon for public pages.
- Replaced text-based "BatchTrack" branding in shared headers with the uploaded full logo artwork.
- Added explicit asset routes to serve attached branding SVG files from stable URLs.
- Added a cropped header-logo variant route so the full logo renders at readable size in nav bars.
- Rolled back the overly broad homepage green-tint overrides to keep branding changes targeted.

## Problems Solved
- The homepage and public shell did not use the provided brand assets for favicon and header identity.
- Header branding depended on text/icon placeholders instead of canonical logo art.
- There was no stable route for serving attached branding SVG files inside templates.

## Key Changes
- `app/__init__.py`
  - Added `/branding/full-logo.svg` and `/branding/app-tile.svg` routes.
  - Added `/branding/full-logo-header.svg` route with viewBox cropping for header legibility.
  - Added shared brand asset file-serving helper for attached SVG files.
  - Bumped homepage cache key default to `public:homepage:v2` so updated branding appears immediately.
  - Completed required functional unit header metadata (Purpose/Inputs/Outputs) for top-level units.
- `app/templates/components/shared/public_marketing_header.html`
  - Replaced the text/flask-icon navbar brand with the cropped full logo image route.
- `app/templates/layout.html`
  - Added favicon links (`icon`, `shortcut icon`, `apple-touch-icon`) using the app tile route.
  - Replaced the authenticated shell text navbar brand with the cropped full logo image route.
  - Added logo sizing styles for shared header contexts.
- `app/templates/homepage.html`
  - Added favicon links (`icon`, `shortcut icon`, `apple-touch-icon`) using the app tile route.
  - Added full-logo sizing styles for homepage header rendering.
  - Removed broad custom green overrides to keep default homepage styling intact.
- `docs/system/APP_DICTIONARY.md`
  - Added route glossary entry for the new branding asset endpoints.

## Files Modified
- `app/__init__.py`
- `app/templates/components/shared/public_marketing_header.html`
- `app/templates/layout.html`
- `app/templates/homepage.html`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-12-homepage-brand-logo-and-favicon-integration.md` (this file)
