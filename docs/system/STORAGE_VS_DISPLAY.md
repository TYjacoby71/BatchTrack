# Storage vs Display: DateTime Best Practices

## The Golden Rule

**STORAGE ≠ DISPLAY**

This is the single most important principle for datetime handling in BatchTrack.

---

## Quick Reference

| Layer | Timezone | Format | Example |
|-------|----------|--------|---------|
| **Database** | UTC (aware) | `datetime.now(timezone.utc)` | `2025-10-28 14:30:00+00:00` |
| **Templates** | User's local | `{{ dt \| user_timezone }}` | `Oct 28, 2025 10:30 AM EDT` |
| **API (storage)** | UTC (ISO 8601) | `dt.isoformat()` | `2025-10-28T14:30:00+00:00` |
| **API (display)** | User's local | `format_datetime_for_api(dt)` | See below |

---

## Project Standard (2025-11-03)

- **Persistence**: Use `TimezoneUtils.utc_now()` (or `datetime.now(timezone.utc)`) when writing timestamps; never persist naive datetimes.
- **Normalization**: Call `TimezoneUtils.ensure_timezone_aware()` on any external or user-provided datetime values before storing/comparing.
- **Presentation**: Rely on the Jinja filters registered in `app/utils/template_filters.py` (`user_timezone`, `user_date`, `user_time`, etc.) for UI rendering.
- **Legacy Utilities**: `TimezoneUtils.convert_to_timezone()` is retained only for backward compatibility; new code should use `to_user_timezone()` / `format_for_user()`.
- **Banned APIs**: `datetime.utcnow()` and bare `datetime.now()` are no longer allowed in code or tests.

## Storage Layer (Database)

### Rule: Always Store in UTC

**DO:**
```python
from datetime import datetime, timezone

# Model definitions
class Batch(db.Model):
    # STORAGE: All times stored as timezone-aware UTC
    # DISPLAY: Templates/APIs convert to user's timezone
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

# Setting values
batch.completed_at = datetime.now(timezone.utc)
reservation.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
```

**DON'T:**
```python
# ❌ WRONG - Naive datetime
batch.completed_at = datetime.now()

# ❌ WRONG - User's local time  
user_dt = TimezoneUtils.to_user_timezone(datetime.now(timezone.utc))
batch.completed_at = user_dt
```

### Why Store in UTC?

1. **Consistency**: All records in the same timezone
2. **Comparisons**: Safe datetime comparisons
3. **Synchronization**: Easy to sync across systems
4. **DST**: No ambiguity during DST transitions
5. **Multi-tenant**: Users in different timezones see accurate relative times

---

## Display Layer (Templates/UI)

### Rule: Always Convert to User's Timezone

**DO:**
```html
<!-- Always use timezone filters -->
{{ batch.started_at | user_timezone }}
{{ batch.completed_at | user_datetime('%Y-%m-%d %H:%M') }}
{{ reservation.expires_at | user_date }}

<!-- Available filters -->
{{ dt | user_timezone }}              <!-- Default format: 2025-10-28 10:30 -->
{{ dt | user_timezone('%B %d, %Y') }} <!-- Custom format: October 28, 2025 -->
{{ dt | user_datetime }}              <!-- With seconds: 2025-10-28 10:30:45 -->
{{ dt | user_date }}                  <!-- Date only: Oct 28, 2025 -->
```

**DON'T:**
```html
<!-- ❌ WRONG - Shows UTC to all users -->
{{ batch.started_at.strftime('%Y-%m-%d %H:%M') }}

<!-- ❌ WRONG - Naive datetime conversion -->
{{ batch.started_at.replace(hour=batch.started_at.hour - 5) }}
```

### Why Convert for Display?

1. **User Experience**: Users see times in familiar context
2. **Local Relevance**: "2 hours ago" means something different in NYC vs Tokyo
3. **Business Hours**: Users understand if something happened during their business hours
4. **Clarity**: No mental math required

---

## API Layer (Integration)

### Rule: Provide BOTH Formats

**DO:**
```python
from app.utils.api_datetime_helpers import format_datetime_for_api

@app.route('/api/batch/<int:batch_id>')
def get_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    
    return jsonify({
        'id': batch.id,
        'status': batch.status,
        # Provides both UTC and user's timezone
        'started_at': format_datetime_for_api(batch.started_at),
        'completed_at': format_datetime_for_api(batch.completed_at)
    })

# Returns:
{
    "id": 123,
    "status": "completed",
    "started_at": {
        "utc": "2025-10-28T14:30:00+00:00",       # For storage/sync
        "local": "2025-10-28T10:30:00-04:00",     # For display
        "display": "Oct 28, 2025 10:30 AM EDT",   # Human-readable
        "timezone": "America/New_York"             # Explicit TZ
    }
}
```

**DON'T:**
```python
# ❌ WRONG - Ambiguous timezone
return jsonify({
    'started_at': batch.started_at.strftime('%Y-%m-%d %H:%M')
})

# ❌ WRONG - Only user's timezone (external systems can't convert)
return jsonify({
    'started_at': TimezoneUtils.to_user_timezone(batch.started_at).isoformat()
})
```

### Why Provide Both?

1. **Flexibility**: API consumers choose their preferred format
2. **Clarity**: No timezone confusion
3. **Debugging**: Easy to verify times
4. **Integration**: External systems can store/display appropriately

---

## Comparison Layer (Business Logic)

### Rule: Always Compare in UTC

**DO:**
```python
from datetime import datetime, timezone
from app.utils.datetime_helpers import ensure_timezone_aware

# Safe comparison (handles both aware and naive)
@property
def is_expired(self):
    """
    Check if reservation has expired.
    
    STORAGE: expires_at stored in UTC (timezone-aware)
    COMPARISON: Safe comparison with current UTC time
    """
    if not self.expires_at:
        return False
    expires_at = ensure_timezone_aware(self.expires_at)
    return datetime.now(timezone.utc) > expires_at

# Direct comparison (if you know both are timezone-aware)
if batch.completed_at and batch.completed_at > datetime.now(timezone.utc):
    raise ValueError("Cannot complete batch in the future")
```

**DON'T:**
```python
# ❌ WRONG - Comparing naive datetime with aware datetime
if datetime.now() > batch.expires_at:  # TypeError!
    mark_as_expired()

# ❌ WRONG - Comparing user's local time with UTC storage
user_now = TimezoneUtils.to_user_timezone(datetime.now(timezone.utc))
if user_now > batch.expires_at:  # Wrong timezone!
    mark_as_expired()
```

---

## Common Scenarios

### Scenario 1: User Creates a Batch

```python
# Service layer (business logic)
def start_batch(product_id, quantity):
    batch = Batch(
        product_id=product_id,
        quantity=quantity,
        started_at=datetime.now(timezone.utc),  # STORAGE: UTC
        organization_id=current_user.organization_id
    )
    db.session.add(batch)
    db.session.commit()
    return batch

# Template (display)
<p>Batch started: {{ batch.started_at | user_timezone }}</p>
<!-- User in New York sees: "2025-10-28 10:30 AM"
     User in Tokyo sees: "2025-10-28 11:30 PM" (same moment, different display) -->
```

### Scenario 2: Setting Reservation Expiration

```python
# Service layer
def create_reservation(order_id, duration_hours=24):
    reservation = Reservation(
        order_id=order_id,
        created_at=datetime.now(timezone.utc),  # STORAGE: UTC
        expires_at=datetime.now(timezone.utc) + timedelta(hours=duration_hours)  # STORAGE: UTC
    )
    db.session.add(reservation)
    db.session.commit()
    
    # API response
    return {
        'reservation_id': reservation.id,
        'expires_at': format_datetime_for_api(reservation.expires_at)  # Both formats
    }
```

### Scenario 3: Checking if Batch is Recent

```python
# Business logic - always in UTC
def get_recent_batches(hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)  # STORAGE: UTC
    return Batch.query.filter(
        Batch.started_at >= cutoff  # Safe comparison (both UTC)
    ).all()

# Template display
{% for batch in recent_batches %}
    <p>{{ batch.product.name }}: {{ batch.started_at | user_timezone }}</p>
    <!-- DISPLAY: Converts to user's timezone -->
{% endfor %}
```

---

## Migration Checklist

If you're updating existing code:

- [ ] Change `datetime.utcnow()` → `datetime.now(timezone.utc)`
- [ ] Update model defaults: `default=datetime.utcnow` → `default=lambda: datetime.now(timezone.utc)`
- [ ] Replace template `.strftime()` → `| user_timezone` filter
- [ ] Use `ensure_timezone_aware()` for comparisons with database datetimes
- [ ] Update API responses to use `format_datetime_for_api()`
- [ ] Add comments: `# STORAGE:` and `# DISPLAY:` for clarity
- [ ] Test with users in different timezones

---

## Helper Functions

### For Safe Comparisons
```python
from app.utils.datetime_helpers import ensure_timezone_aware, safe_datetime_compare

# Handles both aware and naive datetimes
dt = ensure_timezone_aware(some_datetime)

# Safe comparison
if safe_datetime_compare(dt1, dt2):
    # ...
```

### For API Responses
```python
from app.utils.api_datetime_helpers import (
    format_datetime_for_api,
    batch_datetime_response,
    reservation_datetime_response
)

# Single datetime
return jsonify(format_datetime_for_api(batch.started_at))

# Complete batch response
return jsonify(batch_datetime_response(batch))
```

### For Display
```python
from app.utils.timezone_utils import TimezoneUtils

# In Python (e.g., for emails)
user_time = TimezoneUtils.to_user_timezone(batch.started_at)
formatted = user_time.strftime('%B %d, %Y at %I:%M %p %Z')

# In templates (preferred)
{{ batch.started_at | user_timezone('%B %d, %Y at %I:%M %p') }}
```

---

## Testing

Always test with multiple timezones:

```python
# Test fixture
@pytest.fixture
def batch_with_times():
    batch = Batch(
        started_at=datetime(2025, 10, 28, 14, 30, tzinfo=timezone.utc)
    )
    return batch

def test_batch_display_in_different_timezones(batch_with_times):
    # Test NYC user sees 10:30 AM
    user_tz = 'America/New_York'
    display_time = TimezoneUtils.to_user_timezone(
        batch_with_times.started_at, 
        user_tz
    )
    assert display_time.hour == 10  # 14:30 UTC = 10:30 EDT
    
    # Test Tokyo user sees 11:30 PM
    user_tz = 'Asia/Tokyo'
    display_time = TimezoneUtils.to_user_timezone(
        batch_with_times.started_at,
        user_tz
    )
    assert display_time.hour == 23  # 14:30 UTC = 23:30 JST
```

---

## Summary

| What | Where | How |
|------|-------|-----|
| **Store** | Database | `datetime.now(timezone.utc)` |
| **Display** | Templates | `{{ dt \| user_timezone }}` |
| **Compare** | Business Logic | `ensure_timezone_aware(dt)` then compare in UTC |
| **API Response** | Endpoints | `format_datetime_for_api(dt)` |
| **Never** | Anywhere | Mix storage and display timezones |

**Remember**: UTC in the database, user's timezone in the UI. Always.
