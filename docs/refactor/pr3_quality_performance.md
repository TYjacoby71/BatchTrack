
# PR3: Code Quality & Performance (Complete Implementation Plan)

## Overview
Phase 3 focuses on code quality improvements, performance optimization, and security hardening while maintaining the stable foundation built in Phases 1-2. This plan incorporates comprehensive partner feedback for tighter, more incremental delivery.

## Current Progress Assessment

### ✅ Phase 2 Complete: Structural Cleanup
- **Canonical Service**: `app/services/inventory_adjustment.py::process_inventory_adjustment()` fully implemented
- **All Routes Updated**: Batch operations, inventory adjustments use canonical service
- **Legacy Compatibility**: Backwards-compatible shims in place
- **Test Suite**: 24/24 tests passing (characterization tests lock behavior)
- **Business Logic**: Moved out of route handlers

### 🎯 Phase 3 Goals
1. **Service Consolidation** - Hardened external service integrations with idempotency
2. **Route Optimization** - Thin routes with validation layer and uniform error handling
3. **Type Safety** - Strategic typing implementation with mypy
4. **Performance** - Targeted database optimization and N+1 elimination
5. **Security** - Production-ready security headers and rate limiting

## Incremental Delivery Strategy (Recommended)

### PR3a: Service Consolidation (Week 1)
**Focus**: External service hardening with proper idempotency

#### Stripe Service Hardening
- [ ] **Events Table**: `stripe_events` with `event_id` UNIQUE, `processed_at`, `status`, `payload_hash`
```sql
CREATE TABLE stripe_events (
    id SERIAL PRIMARY KEY,
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    payload_hash VARCHAR(64) NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
- [ ] **Idempotent Processing**: Upsert then process; wrap in DB transaction
- [ ] **Interface**: `BillingService.handle_webhook_event(event)` that's idempotent by design
- [ ] **Error Recovery**: Failed event retry with exponential backoff
- [ ] **Webhook Security**: Signature verification → idempotency check → process → mark processed (fail closed)

#### OAuth Service Security
- [ ] **PKCE + State**: Enable code challenge/verifier + state validation
- [ ] **Secure Cookies**: `Secure=True, HttpOnly=True, SameSite=Lax`
- [ ] **Nonce Rotation**: Generate and validate nonce properly
- [ ] **Rate Limits**: Direct limits on `/auth/*` endpoints (Flask-Limiter)
- [ ] **CSRF Protection**: All auth forms protected

#### Service Interface Design
- [ ] **Abstract Classes**: Define interfaces/ports for external services
```python
from abc import ABC, abstractmethod
from typing import Dict, TypedDict, Optional
from datetime import datetime

class WebhookResult(TypedDict):
    success: bool
    message: str
    processed_at: Optional[datetime]
    event_id: str

class BillingServiceInterface(ABC):
    @abstractmethod
    def handle_webhook_event(self, event_data: Dict) -> WebhookResult:
        pass
    
    @abstractmethod
    def create_subscription(self, customer_id: str, price_id: str) -> Dict:
        pass

class OAuthServiceInterface(ABC):
    @abstractmethod
    def generate_auth_url(self, state: str, nonce: str) -> str:
        pass
    
    @abstractmethod
    def handle_callback(self, code: str, state: str) -> Dict:
        pass
```
- [ ] **Dependency Injection**: Routes depend on abstractions, not implementations
- [ ] **Testing**: Enable easy mocking and provider swaps

### PR3b: Route Thinning & Validation (Week 2)
**Focus**: Parse → Service → Jsonify pattern with validation

#### Validation Layer
- [ ] **Pydantic Schemas**: All request/response bodies in `app/schemas/`
```python
# app/schemas/inventory.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class InventoryAdjustmentRequest(BaseModel):
    quantity: float = Field(..., gt=0, description="Quantity to adjust")
    change_type: str = Field(..., regex="^(restock|spoil|trash|damaged|manual|recount|sale|reserved|unreserved)$")
    notes: Optional[str] = Field(None, max_length=500)
    expiration_date: Optional[datetime] = None
    lot_number: Optional[str] = Field(None, max_length=100)

class InventoryAdjustmentResponse(BaseModel):
    success: bool
    message: str
    item_id: int
    new_quantity: float
    adjustment_id: int
    timestamp: datetime
```

- [ ] **Uniform Error Envelope**: `{"error":{"code","message","details"}}`
```python
# app/schemas/errors.py
from pydantic import BaseModel
from typing import Optional, Dict, Any

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field: Optional[str] = None

class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    request_id: Optional[str] = None
    timestamp: datetime
```

- [ ] **Exception Mapper**: Centralized HTTP status + error code mapping
- [ ] **Input Sanitization**: Comprehensive validation and sanitization

#### Route Optimization
- [ ] **Business Logic Extraction**: Move complex logic to services
- [ ] **Standardized Flow**: Routes: parse → service → jsonify
```python
# Example pattern for all routes
@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
@require_permission('inventory.adjust')
def adjust_inventory(id: int):
    try:
        # Parse & validate
        data = InventoryAdjustmentRequest.model_validate(request.json)
        
        # Service call
        result = inventory_service.adjust_inventory(
            item_id=id,
            quantity=data.quantity,
            change_type=data.change_type,
            notes=data.notes,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        # Response
        return jsonify(InventoryAdjustmentResponse(**result))
        
    except ValidationError as e:
        return jsonify(ErrorEnvelope(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Invalid request data",
                details=e.errors()
            ),
            request_id=g.request_id
        )), 400
    except InventoryServiceError as e:
        return jsonify(ErrorEnvelope(
            error=ErrorDetail(
                code=e.error_code,
                message=str(e),
                details=e.details
            ),
            request_id=g.request_id
        )), e.http_status
```
- [ ] **Target LOC**: Routes ≤ 100 LOC average in target blueprints
- [ ] **Error Consistency**: Uniform error responses across all endpoints

### PR3c: Type Safety, Performance & Security (Week 3)
**Focus**: Production readiness with monitoring

#### Type Safety Implementation
- [ ] **MyPy Config**: Add comprehensive `mypy.ini`
```ini
[mypy]
python_version = 3.11
warn_unused_ignores = True
warn_redundant_casts = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
ignore_missing_imports = True
strict_optional = True
no_implicit_optional = True

[mypy-app.services.*]
disallow_untyped_defs = True
disallow_any_generics = True

[mypy-app.models.*]
disallow_untyped_defs = True

[mypy-migrations.*]
ignore_errors = True

[mypy-tests.*]
disallow_untyped_defs = False
```
- [ ] **Strict Services**: `disallow-untyped-defs = True` in `app/services/**`
- [ ] **Typed Returns**: TypedDict/Pydantic models for service JSON shapes
- [ ] **Target Coverage**: ≥80% type coverage in service layer

#### Database Performance
- [ ] **Strategic Indexes** (Alembic migrations):
```python
# Migration: add_performance_indexes.py
def upgrade():
    # Inventory performance
    op.create_index('idx_inventory_history_item_qty', 'inventory_history', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_inventory_history_item_exp', 'inventory_history', ['inventory_item_id', 'expiration_date'])
    op.create_index('idx_inventory_history_org_time', 'inventory_history', ['organization_id', 'timestamp'])
    
    # Product SKU performance  
    op.create_index('idx_product_sku_history_item_qty', 'product_sku_history', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_product_sku_history_item_exp', 'product_sku_history', ['inventory_item_id', 'expiration_date'])
    
    # Audit performance
    op.create_index('idx_audit_log_org_created', 'audit_log', ['organization_id', 'created_at'])
    
    # User/org performance
    op.create_index('idx_user_org_active', 'user', ['organization_id', 'is_active'])
```
- [ ] **N+1 Elimination**: Apply `selectinload/joinedload` in hot paths
```python
# Example: Fix N+1 in recipe ingredients
def get_recipe_with_ingredients(recipe_id: int):
    return db.session.query(Recipe)\
        .options(
            selectinload(Recipe.recipe_ingredients)
            .selectinload(RecipeIngredient.inventory_item)
            .selectinload(InventoryItem.ingredient)
        )\
        .filter_by(id=recipe_id)\
        .first()
```
- [ ] **Query Monitoring**: Log >100ms queries with route + query count
```python
# app/utils/performance_monitor.py
import time
import logging
from sqlalchemy import event
from flask import g, request

logger = logging.getLogger(__name__)

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    if not hasattr(g, 'query_count'):
        g.query_count = 0
    g.query_count += 1

@event.listens_for(Engine, "after_cursor_execute") 
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    if total > 0.1:  # Log queries >100ms
        route = getattr(request, 'endpoint', 'unknown') if request else 'unknown'
        logger.warning(
            f"Slow query in {route} ({total:.3f}s, query #{g.query_count}): {statement[:200]}...",
            extra={
                'query_time': total,
                'route': route,
                'query_count': g.query_count,
                'statement_preview': statement[:200]
            }
        )
```

#### Security Hardening
- [ ] **Form Protection**: CSRF on all forms
```python
# app/utils/security.py
from flask_wtf.csrf import CSRFProtect, validate_csrf
from flask import request, abort

csrf = CSRFProtect()

def require_csrf():
    """Decorator to require CSRF token on API endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                try:
                    validate_csrf(request.headers.get('X-CSRFToken'))
                except:
                    abort(403, description="CSRF token missing or invalid")
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```
- [ ] **Security Headers**: Global CSP + Referrer-Policy, HSTS in production
```python
# app/utils/security.py
@app.after_request
def set_security_headers(response):
    if app.config.get('ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://js.stripe.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.stripe.com; "
        "frame-src https://js.stripe.com"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response
```
- [ ] **Brute Force Protection**: Rate limits on login, password reset
```python
# app/utils/rate_limiting.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

# Apply to auth routes
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    # login logic
    pass

@auth_bp.route('/webhook', methods=['POST'])  
@limiter.limit("100 per minute")
def stripe_webhook():
    # webhook logic
    pass
```

## CI/CD Pipeline Enhancement

### Quality Gates (All PRs)
- [ ] **pytest**: All tests must pass
- [ ] **ruff**: Code formatting and linting
- [ ] **mypy**: Type checking (strict mode for services)
- [ ] **bandit**: Security scanning
- [ ] **Migration Check**: Ensure no drift or multiple heads

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11" }
    
    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov mypy ruff black isort bandit
    
    - name: Lint
      run: |
        ruff check app tests
        black --check app tests
        isort --check-only app tests
    
    - name: Security scan
      run: bandit -r app -f json
    
    - name: Type check
      run: mypy app
    
    - name: Migration check
      run: |
        export DATABASE_URL=postgresql://postgres:postgres@localhost/test_db
        flask db upgrade
        flask db check  # Custom command to verify no drift
    
    - name: Tests
      run: |
        export DATABASE_URL=postgresql://postgres:postgres@localhost/test_db
        pytest --cov=app --cov-report=xml
        
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Smoke Tests
- [ ] **Post-deploy**: Hit key routes after deployment
- [ ] **Performance Guard**: Ensure hot paths execute ≤ N queries
- [ ] **Security Validation**: CSRF, headers, rate limits active

## Success Metrics (Sharpened)

### Code Quality
- [ ] Routes ≤ 100 LOC average in target blueprints
- [ ] Service methods: 100% typed
- [ ] Overall service layer: ≥80% typed  
- [ ] Zero direct external service calls from routes

### Performance
- [ ] P99 route latency ≤ 200ms (dev/proxy env)
- [ ] Zero known N+1 on critical paths
- [ ] Strategic indexes deployed and monitored
- [ ] Query timing logs active

### Security
- [ ] CSRF on all forms
- [ ] CSP present with proper directives
- [ ] Webhook sig/idempotency enforced
- [ ] Rate limiting on auth endpoints
- [ ] OAuth PKCE + state validation

### Development Experience
- [ ] Type errors caught in CI
- [ ] Uniform error responses
- [ ] Easy service mocking for tests
- [ ] Performance regression detection

## Testing Strategy (Minimal, High-Value)

### Service Layer Tests
- [ ] **Stripe Idempotency**: Same event twice → processed once
- [ ] **OAuth Security**: State/nonce/PKCE negative cases
- [ ] **Route Thinness**: Unit tests asserting routes only call service + return mapped results

### Performance Guards
```python
# tests/test_performance.py
import pytest
from app.utils.performance_monitor import QueryCounter

def test_recipe_ingredients_no_n_plus_1():
    """Ensure recipe with ingredients loads in ≤3 queries"""
    with QueryCounter() as counter:
        recipe = get_recipe_with_ingredients(recipe_id=1)
        assert len(recipe.recipe_ingredients) > 0
    assert counter.count <= 3, f"N+1 detected: {counter.count} queries"

def test_inventory_list_performance():
    """Critical endpoint must respond quickly"""
    with QueryCounter() as counter:
        start = time.time()
        response = client.get('/inventory/')
        duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.2, f"Too slow: {duration:.3f}s"
    assert counter.count <= 10, f"Too many queries: {counter.count}"
```

### Security Tests
- [ ] **CSRF**: Forms reject requests without valid tokens
- [ ] **Rate Limiting**: Auth endpoints properly throttle
- [ ] **Headers**: Security headers present in responses

## Test & Shim Cleanup Strategy

### Complete Shim Inventory (Added During PR2)

#### Service Layer Compatibility Shims
**In `app/services/inventory_adjustment.py`:**
- [ ] `InventoryAdjustmentService` class (lines 672-685) - Backwards compatibility wrapper
- [ ] `record_audit_entry()` duplicate function (lines 657-687) - Legacy signature support

**In `app/blueprints/fifo/services.py`:**
- [ ] `FIFOService` class (lines 46-100) - Compatibility wrapper for old FIFO calls
- [ ] `get_fifo_entries()` and `get_expired_fifo_entries()` global functions (lines 450-460)
- [ ] `recount_fifo()` global function (line 462)
- [ ] Entire module marked as "INTERNAL USE ONLY" with deprecation warnings

**In `app/services/stock_check.py`:**
- [ ] `StockCheckService` class (lines 114-147) - Backwards compatibility wrapper with deprecation warnings
- [ ] Legacy function signatures that bypass canonical service

#### Model Import Compatibility
**In `app/blueprints/fifo/__init__.py`:**
- [ ] `DeprecatedFIFOModule` override (lines 17-35) - Intercepts direct imports with warnings
- [ ] Import monitoring system for external access detection

#### Route Compatibility Layers
**Test fixtures and route shims:**
- [ ] Multiple test files with mock compatibility layers
- [ ] Route handlers that still import deprecated services directly
- [ ] Legacy parameter handling in API endpoints

#### Database Migration Compatibility
**Multiple migration files with legacy field support:**
- [ ] `39e309ff02d1_add_legacy_compatibility_fields_to_.py` - Stripe billing compatibility
- [ ] `add_legacy_compatibility_fields.py` - General backward compatibility
- [ ] `replace_billing_booleans_with_enums.py` - Billing system transition support

### When to Remove Tests and Shims

#### Phase 3 Completion (After PR3c)
**Remove characterization test shims:**
- [ ] Remove test fixtures that mock old behavior
- [ ] Replace characterization tests with proper unit/integration tests
- [ ] Remove backwards compatibility shims in `inventory_adjustment.py`
- [ ] Clean up duplicate test scenarios

#### Phase 4 (Post-Production)
**Remove legacy compatibility:**
- [ ] Remove old route handlers marked as deprecated
- [ ] Remove unused service methods
- [ ] Clean up model backwards compatibility fields
- [ ] Remove development-only test utilities

#### Criteria for Cleanup (Partner's Timeline)
1. **PR3 (Now)** - Deprecate, don't delete (add warnings, instrument usage)
2. **PR3+1 Release** - Observe for 7 days with zero usage confirmation
3. **PR4** - Safe removal with CI guardrails

### Cleanup Priority Order (Partner-Aligned)
1. **Service compatibility wrappers** - `StockCheckService`, `FIFOService`, `InventoryAdjustmentService`
2. **Global function aliases** - `get_fifo_entries()`, `recount_fifo()` module-level functions
3. **Import monitoring systems** - `DeprecatedFIFOModule` in `__init__.py`
4. **Test fixture shims** - Mock compatibility layers in test files
5. **Legacy migration fields** - Database backward compatibility columns

### Immediate PR3 Actions (Deprecation Phase)
**Add to all remaining shims:**
```python
import warnings
warnings.warn(
    "This compatibility layer will be removed in the next release. Use canonical service.",
    DeprecationWarning,
    stacklevel=2
)
```

**Add usage instrumentation:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"DEPRECATED_SHIM_USAGE: {caller_module}:{caller_function}")
```

**Feature flag for staging:**
```python
# In config
FEATURE_DISABLE_SHIMS = os.environ.get('FEATURE_DISABLE_SHIMS', 'False').lower() == 'true'
```

## Migration from Current State

### Phase 2 Complete Prerequisites ✅
- Canonical inventory service (`process_inventory_adjustment`) stable
- All inventory changes flow through canonical service
- Test suite: 24/24 tests passing
- Legacy shims removed, business logic out of routes

### Risk Mitigation
- **Backwards Compatibility**: Service interfaces maintain existing signatures initially
- **Performance Monitoring**: Benchmark before/after for regression detection  
- **Incremental Security**: Add security features progressively, not all-or-nothing
- **CI/CD Safety**: Quality gates prevent broken code from merging

## Alternative: Single PR3 (Original Plan)
If team prefers single large PR:
- Complete all work in one comprehensive PR
- More thorough integration testing
- Single large code review
- Higher risk but potentially faster if no issues

**Recommendation**: Use incremental delivery (PR3a/b/c) for safer, faster feedback cycles.

## Next Steps After PR3

### Phase 4: Production Readiness
- Production environment configuration
- Monitoring and alerting setup  
- Backup and disaster recovery
- Performance monitoring dashboard
- User documentation and API specs

### Phase 5: Test & Shim Cleanup
- Remove characterization test shims
- Clean up backwards compatibility layers
- Optimize test suite for maintainability
- Document final architecture

**Target**: Production-ready codebase with enterprise-grade quality, security, and performance characteristics.

## Current Action Items (Immediate)

### Week 1 Focus
1. **Run pytest** to confirm all 24 tests still pass
2. **Implement PR3a** - Service consolidation with Stripe idempotency
3. **Add performance monitoring** to catch regressions
4. **Set up CI/CD pipeline** with quality gates

### Success Checkpoints
- [ ] Stripe webhooks are idempotent and secure
- [ ] OAuth has proper PKCE + state validation
- [ ] All external service calls go through abstractions
- [ ] CI catches type errors and security issues

**Status**: Ready to begin PR3a - Service Consolidation
