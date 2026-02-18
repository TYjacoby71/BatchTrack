## Summary
Added optional first-party website monitoring bootstrap support for GA4 and PostHog, wired through environment configuration and rendered in the shared application layout. This gives deployments immediate page-traffic visibility without page-by-page template edits.

## Problems Solved
- Operators could not easily measure top-level site traffic after deploy.
- There was no built-in bridge between app config and external analytics providers.
- Integrations guidance did not clearly explain GA4 vs PostHog positioning.

## Key Changes
- Added analytics config schema keys under operations:
  - `GOOGLE_ANALYTICS_MEASUREMENT_ID`
  - `POSTHOG_PROJECT_API_KEY`
  - `POSTHOG_HOST`
  - `POSTHOG_CAPTURE_PAGEVIEW`
  - `POSTHOG_CAPTURE_PAGELEAVE`
- Exposed the new values from `app.config` runtime settings.
- Updated the shared layout to conditionally inject:
  - GA4 `gtag.js` + `gtag('config', ...)`
  - PostHog browser bootstrap + `posthog.init(...)`
- Added regression tests to verify scripts render only when configured.
- Updated tracking documentation and app dictionary references for the new monitoring surface.

## Files Modified
- `app/config_schema_parts/operations.py`
- `app/config.py`
- `app/templates/layout.html`
- `tests/test_traffic_analytics_scripts.py`
- `docs/system/TRACKING_PLAN.md`
- `docs/system/APP_DICTIONARY.md`
