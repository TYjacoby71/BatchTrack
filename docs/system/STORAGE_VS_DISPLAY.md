# Storage vs Display: DateTime Best Practices

## Synopsis
This guide defines the non-negotiable datetime rule in BatchTrack: store UTC, display user-local time. It documents the current helper APIs and rendering filters used in app code and templates.

## Glossary
- **Storage timestamp**: Datetime persisted to the database (UTC, timezone-aware).
- **Display timestamp**: Datetime rendered for a specific user timezone.
- **Normalization**: Converting naive/unknown datetimes into timezone-aware values before comparison.

## Golden Rule
**STORAGE != DISPLAY**

| Concern | Standard |
|---|---|
| Persistence | Use timezone-aware UTC (`TimezoneUtils.utc_now()` or `datetime.now(timezone.utc)`) |
| Rendering | Use user-timezone filters/functions (`user_timezone`, `user_datetime`, `TimezoneUtils.format_for_user`) |
| API payloads | Prefer structured UTC + local output (`TimezoneUtils.format_datetime_for_api`) |
| Comparisons | Normalize first with `TimezoneUtils.ensure_timezone_aware` and compare in UTC |

## Required Patterns

### 1) Store UTC in models/services
- Good: `created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)`
- Avoid: `datetime.utcnow()` or bare `datetime.now()`

### 2) Render with template filters
- Good: `{{ batch.started_at | user_timezone }}`
- Good: `{{ dt | user_date }}`
- Avoid: inline `strftime` on raw UTC values for user-facing pages.

### 3) Normalize before comparison
- Good: `aware = TimezoneUtils.ensure_timezone_aware(dt)`
- Then compare against `datetime.now(timezone.utc)` (or equivalent UTC-aware values).

### 4) API responses
- Use `TimezoneUtils.format_datetime_for_api(dt)` when returning mixed machine/human datetime context.

## Common Mistakes to Avoid
- Writing user-local datetimes into DB fields.
- Comparing naive and aware datetimes directly.
- Manual timezone math in templates/JS (for example subtracting hours).
- Returning ambiguous datetime strings without timezone context.

## Relevance Check (2026-02-17)
Validated against:
- `app/utils/timezone_utils.py`
- `app/utils/template_filters.py`
- `app/blueprints/settings/routes.py`
- `app/services/timer_service.py`
- `app/models/*` timestamp defaults using `TimezoneUtils.utc_now` or UTC-aware datetimes
