## Summary
- Fixed timer rendering issues across batch in-progress and timer management pages.
- Removed mixed timezone arithmetic paths that caused batch in-progress page redirects/errors.
- Hardened timer frontend parsing to avoid invalid-date math and `NaN` countdown displays.

## Problems Solved
- Batch in-progress timer math could raise `can't subtract offset-naive and offset-aware datetimes` when active timers were present.
- Timer management countdown display could render broken text (for example `NaNm NaNs`) when timestamp parsing failed.
- Missing regression coverage for this pair of timer rendering failure modes.

## Key Changes
- Normalized datetime arithmetic in the batch timer component template by using safe, naive values for display math:
  - `now_for_timer_math`
  - `timer_start_for_math`
  - `timer_end_for_math`
- Added robust timestamp parsing in timer management JavaScript with `parseTimerStart(timer)` and safer numeric guards in duration/countdown calculations.
- Added targeted regression tests for:
  - in-progress batch rendering with active timer data
  - safe timer-list template parsing behavior

## Files Modified
- `app/templates/components/batch/timer_component.html`
- `app/blueprints/timers/templates/timer_list.html`
- `tests/test_batch_timer_datetime_render.py`
