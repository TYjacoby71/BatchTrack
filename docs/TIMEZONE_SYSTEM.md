
# BatchTrack Timezone System Documentation

## Overview

BatchTrack implements a **user-centric timezone system** where each user can set their preferred timezone while all data is stored in UTC. This approach ensures data consistency across a multi-tenant SaaS environment while providing localized time displays for users worldwide.

## Core Architecture

### 1. Storage Strategy
- **Database Storage**: All timestamps stored in UTC (timezone-naive datetime objects)
- **User Preferences**: Each user has a `timezone` field storing their preferred timezone string
- **Display Layer**: Times converted to user's timezone for display only
- **API Responses**: All API endpoints return times in user's timezone when applicable

### 2. Key Components

#### TimezoneUtils (`app/utils/timezone_utils.py`)
Central utility class providing all timezone operations:

```python
# Core methods
TimezoneUtils.utc_now()                    # Get current UTC time
TimezoneUtils.to_user_timezone(dt)         # Convert UTC to user's timezone  
TimezoneUtils.from_user_timezone(dt)       # Convert user's timezone to UTC
TimezoneUtils.format_for_user(dt, format)  # Format datetime in user's timezone
```

#### User Model Integration
- `User.timezone` field stores user's preferred timezone (e.g., 'US/Eastern')
- Defaults to 'UTC' if not set
- Validated against `pytz.all_timezones`

## Implementation Patterns

### 1. Database Operations

**✅ Correct - Store in UTC:**
```python
from app.utils.timezone_utils import TimezoneUtils

# Creating new records
batch = Batch(
    started_at=TimezoneUtils.utc_now(),  # Always UTC
    organization_id=current_user.organization_id
)
```

**❌ Incorrect - Don't store user timezone:**
```python
# NEVER do this
batch = Batch(
    started_at=TimezoneUtils.now()  # This would be in user's timezone
)
```

### 2. Display Layer

**✅ Correct - Convert for display:**
```python
# In templates or API responses
user_time = TimezoneUtils.to_user_timezone(batch.started_at)
formatted_time = TimezoneUtils.format_for_user(
    batch.started_at, 
    '%Y-%m-%d %H:%M:%S'
)
```

**Template Usage:**
```html
<!-- Automatic user timezone conversion -->
{{ batch.started_at | user_timezone }}

<!-- Custom formatting -->
{{ batch.started_at | user_timezone('%m/%d/%Y %I:%M %p') }}
```

### 3. User Input Processing

**✅ Correct - Convert to UTC before saving:**
```python
# When user submits a datetime
user_input_time = request.form.get('scheduled_time')
parsed_time = datetime.strptime(user_input_time, '%Y-%m-%d %H:%M')

# Convert from user's timezone to UTC for storage
utc_time = TimezoneUtils.from_user_timezone(parsed_time)
batch.scheduled_at = utc_time
```

### 4. API Endpoints

**✅ Correct - Return user-localized times:**
```python
@api.route('/batches/<int:batch_id>')
def get_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    return jsonify({
        'id': batch.id,
        'started_at': TimezoneUtils.format_for_user(batch.started_at),
        'user_timezone': TimezoneUtils.get_user_timezone()
    })
```

## Timezone Selection UI

### Available Timezones
- **Common Timezones**: Priority list of frequently used timezones
- **Regional Grouping**: Organized by North America, Europe, Asia, etc.
- **Display Names**: User-friendly names (e.g., "Eastern Time (US)" instead of "US/Eastern")

### Settings Interface
Located in `/settings` - users can change their timezone preference at any time.

## Migration Considerations

### From Organization-Based to User-Based
BatchTrack previously used organization-level timezones but migrated to user-level for better flexibility:

```python
# Old pattern (deprecated)
org_timezone = current_user.organization.timezone

# New pattern (current)
user_timezone = current_user.timezone or 'UTC'
```

### Database Migration Notes
- All existing timestamps remain in UTC
- No data migration required for timezone changes
- User timezone preferences default to UTC for existing users

## Development Guidelines

### 1. Adding New Datetime Fields

**Always use UTC for storage:**
```python
class NewModel(db.Model):
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)
```

### 2. Working with Expiration Dates

**Special handling for time-sensitive calculations:**
```python
# In ExpirationService
def calculate_expiration_date(start_date: datetime, shelf_life_days: int) -> datetime:
    # Ensure start_date is timezone-aware (UTC)
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    
    # Calculate expiration maintaining timezone
    return start_date + timedelta(days=shelf_life_days)
```

### 3. Timer and Alert Systems

**Use UTC for all time comparisons:**
```python
# Dashboard alerts - always compare in UTC
now_utc = TimezoneUtils.utc_now()
cutoff_time = now_utc - timedelta(hours=24)

stuck_batches = Batch.query.filter(
    Batch.status == 'in_progress',
    Batch.started_at < cutoff_time  # Both in UTC
).all()
```

### 4. Testing Timezone Functionality

**Mock user timezones in tests:**
```python
def test_batch_display_timezone():
    with app.test_client() as client:
        # Set user timezone
        user.timezone = 'US/Pacific'
        
        # Create batch in UTC
        batch = Batch(started_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        
        # Verify display shows Pacific time
        response = client.get(f'/batches/{batch.id}')
        assert 'Jan 01, 2025 04:00 AM' in response.data  # UTC-8
```

## Common Pitfalls

### ❌ Mixing Timezone-Aware and Naive Datetimes
```python
# This will cause errors
aware_dt = datetime.now(timezone.utc)
naive_dt = datetime.now()
diff = aware_dt - naive_dt  # TypeError!
```

### ❌ Using datetime.now() for Storage
```python
# Wrong - depends on server timezone
created_at = datetime.now()

# Correct - always UTC
created_at = TimezoneUtils.utc_now()
```

### ❌ Hardcoding Timezone Conversions
```python
# Wrong - doesn't respect user preference
eastern = datetime.now(pytz.timezone('US/Eastern'))

# Correct - uses user's preference
user_time = TimezoneUtils.to_user_timezone(utc_datetime)
```

## Future Enhancements

### Planned Features
1. **Organization Default Timezone**: Set default timezone for new organization users
2. **Timezone Auto-Detection**: Detect user's timezone from browser
3. **Multiple Timezone Display**: Show times in multiple timezones simultaneously
4. **Batch Timezone Locking**: Lock batch times to creation timezone for consistency

### API Improvements
1. **ISO 8601 Support**: Accept/return ISO format with timezone info
2. **Timezone Negotiation**: Support `Accept-Timezone` headers
3. **Bulk Operations**: Handle timezone conversions in bulk data operations

## Troubleshooting

### Common Issues

**Expiration Calculation Errors:**
```
TypeError: can't subtract offset-naive and offset-aware datetimes
```
**Solution**: Use `TimezoneUtils.utc_now()` and ensure all datetime objects are timezone-aware.

**Display Issues:**
- Times showing in UTC instead of user timezone
- **Solution**: Verify template filters are applied correctly

**User Settings Not Saving:**
- Timezone field not updating
- **Solution**: Check form validation and timezone string format

### Debug Tools

**Check Current User Timezone:**
```python
print(f"User timezone: {TimezoneUtils.get_user_timezone()}")
print(f"UTC now: {TimezoneUtils.utc_now()}")
print(f"User now: {TimezoneUtils.now()}")
```

## Dependencies

- **pytz**: Timezone database and conversion utilities
- **Flask-Login**: User context for timezone preferences
- **SQLAlchemy**: UTC datetime storage

## File Locations

- **Core Utilities**: `app/utils/timezone_utils.py`
- **User Settings**: `app/blueprints/settings/routes.py`
- **Template Filters**: `app/utils/template_filters.py`
- **Expiration Service**: `app/blueprints/expiration/services.py`
- **Dashboard Alerts**: `app/services/dashboard_alerts.py`

---

**⚠️ Critical Rule**: Never bypass `TimezoneUtils` for datetime operations. Always store in UTC, display in user's timezone.
