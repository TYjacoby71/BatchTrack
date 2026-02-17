# Timezone System

## Synopsis
This document describes how BatchTrack handles user timezone preferences, timezone-aware datetime storage, and timezone-safe rendering across templates and APIs. It is the system-level map; see `STORAGE_VS_DISPLAY.md` for day-to-day implementation rules.

## Glossary
- **User timezone**: The timezone string stored on `User.timezone` and used for display.
- **UTC authority**: The requirement that persisted/comparison datetimes are UTC-aware.
- **Timezone presentation layer**: Template filters and formatter helpers that convert UTC to local display output.

## Architecture Overview

### 1) User preference model
- User timezone is stored per account (`User.timezone`).
- Validation is handled through `TimezoneUtils.validate_timezone`.
- Settings flows in `app/blueprints/settings/routes.py` expose timezone updates.

### 2) Utility authority
`app/utils/timezone_utils.py` is the central utility for:
- `utc_now()`
- `to_user_timezone()`
- `from_user_timezone()`
- `format_for_user()`
- `ensure_timezone_aware()`
- `format_datetime_for_api()`
- grouped/region-aware timezone selectors (`get_grouped_timezones`)

### 3) Template layer
Timezone display filters are registered in `app/utils/template_filters.py`, including:
- `user_timezone`
- `user_datetime`
- `user_date`
- `user_time`

### 4) Request/runtime behavior
- Middleware and route handlers keep storage/comparison in UTC.
- UI and response rendering convert to user timezone only at presentation boundaries.

## Current Rules
1. Persist and compare datetimes in UTC-aware format.
2. Normalize external/user-provided datetimes before comparing.
3. Convert to user timezone only when rendering or formatting for display.
4. Avoid `datetime.utcnow()` and bare `datetime.now()` in application code.

## Operational Notes
- Timezone-aware defaults are used across active models/services.
- Timer and scheduling surfaces rely on UTC internally and display-local conversion externally.
- Timezone selection UI supports grouped suggestions and user-friendly labels.

## Related Documentation
- [Storage vs Display Best Practices](STORAGE_VS_DISPLAY.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)

## Relevance Check (2026-02-17)
Validated against:
- `app/utils/timezone_utils.py`
- `app/utils/template_filters.py`
- `app/blueprints/settings/routes.py`
- `app/middleware.py`
- `app/services/timer_service.py`
