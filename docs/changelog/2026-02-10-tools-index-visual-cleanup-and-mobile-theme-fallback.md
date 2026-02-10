# 2026-02-10 — Tools Index Visual Cleanup and Mobile Theme Fallback Fix

## Summary
- Simplified the public tools index visual styling to match core app card/surface styling.
- Removed multi-color/rainbow accent treatment from tool category cards and tool tiles.
- Fixed a mobile dark-theme forcing issue by changing theme bootstrap fallback behavior to explicit light mode when no user theme is selected.
- Updated system dark-mode behavior to require explicit `data-theme='system'` rather than implicit no-attribute matching.
- Added glossary entries in `APP_DICTIONARY.md` for the updated UI/theme behavior.

## Problems Solved
- The `/tools` listing looked overly colorful and inconsistent with the rest of the app interface.
- Phones configured for dark OS mode could push users into dark UI even when they had never selected a theme.
- Theme selection behavior mixed implicit and explicit rules, causing confusing mobile rendering outcomes.

## Key Changes
- `app/templates/tools/index.html`
  - Added template Synopsis/Glossary block.
  - Added canonical metadata variable for `/tools`.
  - Removed per-card accent variables and replaced rainbow tile styling with neutral app-surface styling.
- `app/template_context.py`
  - Added module Synopsis/Glossary docstring.
  - Stopped coercing unset user theme preference to `"system"`; leave unset values as `None`.
- `app/templates/layout.html`
  - Added template Synopsis/Glossary block.
  - Updated theme bootstrap logic to:
    - use server theme only when explicitly set,
    - otherwise fall back to stored theme or light,
    - always apply an explicit `data-theme` attribute.
- `app/templates/settings/components/appearance_tab.html`
  - Added template Synopsis/Glossary block.
  - Updated client-side appearance logic to align with explicit theme application (including `system`).
- `app/static/css/theme.css`
  - Added Synopsis/Glossary comments.
  - Scoped system-dark token overrides to `:root[data-theme='system']` in dark media context.
- `docs/system/APP_DICTIONARY.md`
  - Added entries for System Theme Token behavior and Maker Tools neutral card styling.

## Impact
- Public tools page is visually calmer and closer to the authenticated app styling language.
- Mobile users no longer get dark mode by default unless they intentionally choose System/Dark behavior.
- Theme behavior is now explicit and predictable across devices.

## Files Modified
- `app/templates/tools/index.html`
- `app/template_context.py`
- `app/templates/layout.html`
- `app/templates/settings/components/appearance_tab.html`
- `app/static/css/theme.css`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-10-tools-index-visual-cleanup-and-mobile-theme-fallback.md` (this file)
