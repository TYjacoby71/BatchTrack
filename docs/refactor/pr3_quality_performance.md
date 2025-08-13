# PR3: Code Quality & Performance (Refined)

## Overview
Phase 3 focuses on code quality improvements, performance optimization, and security hardening while maintaining the stable foundation built in Phases 1-2. This plan incorporates partner feedback for tighter, more incremental delivery.

## Goals
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
- [ ] **Idempotent Processing**: Upsert then process; wrap in DB transaction
- [ ] **Interface**: `StripeService.handle_event(event)` that's idempotent by design
- [ ] **Error Recovery**: Failed event retry with exponential backoff

#### OAuth Service Security
- [ ] **PKCE + State**: Enable code challenge/verifier + state validation
- [ ] **Secure Cookies**: `Secure=True, HttpOnly=True, SameSite=Lax`
- [ ] **Nonce Rotation**: Generate and validate nonce properly
- [ ] **Rate Limits**: Direct limits on `/auth/*` endpoints

#### Service Interface Design
- [ ] **Abstract Classes**: Define interfaces/ports for external services
- [ ] **Dependency Injection**: Routes depend on abstractions, not implementations
- [ ] **Testing**: Enable easy mocking and provider swaps

### PR3b: Route Thinning & Validation (Week 2)
**Focus**: Parse → Service → Jsonify pattern with validation

#### Validation Layer
- [ ] **Pydantic Schemas**: All request/response bodies in `schemas/`
- [ ] **Uniform Error Envelope**: `{"error":{"code","message","details"}}`
- [ ] **Exception Mapper**: Centralized HTTP status + error code mapping
- [ ] **Input Sanitization**: Comprehensive validation and sanitization

#### Route Optimization
- [ ] **Business Logic Extraction**: Move complex logic to services
- [ ] **Standardized Flow**: Routes: parse → service → jsonify
- [ ] **Target LOC**: Routes ≤ 100 LOC average in target blueprints
- [ ] **Error Consistency**: Uniform error responses across all endpoints

### PR3c: Type Safety, Performance & Security (Week 3)
**Focus**: Production readiness with monitoring

#### Type Safety Implementation
- [ ] **MyPy Config**: `mypy.ini` with SQLAlchemy plugin
- [ ] **Strict Services**: `disallow-untyped-defs = True` in `app/services/**`
- [ ] **Typed Returns**: TypedDict/Pydantic models for service JSON shapes
- [ ] **Target Coverage**: ≥80% type coverage in service layer

#### Database Performance
- [ ] **Strategic Indexes** (Alembic migrations):
  - `InventoryHistory (inventory_item_id, remaining_quantity)`
  - `InventoryHistory (inventory_item_id, expiration_date)`
  - `InventoryHistory (organization_id, timestamp)`
  - `ProductSKUHistory` equivalents
  - `AuditLog (organization_id, created_at)`
- [ ] **N+1 Elimination**: Apply `selectinload/joinedload` in hot paths
- [ ] **Query Monitoring**: Log >100ms queries with route + query count

#### Security Hardening
- [ ] **Form Protection**: CSRF on all forms
- [ ] **Security Headers**: Global CSP + Referrer-Policy, HSTS in production
- [ ] **Webhook Security**: Signature check → idempotency check → process → mark processed
- [ ] **Brute Force Protection**: Rate limits on login, password reset

## Technical Implementation Details

### 1. Stripe Event Idempotency Table
```sql
CREATE TABLE stripe_events (
    id SERIAL PRIMARY KEY,
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    payload_hash VARCHAR(64) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Service Interface Pattern
```python
from abc import ABC, abstractmethod
from typing import Dict, TypedDict

class WebhookResult(TypedDict):
    success: bool
    message: str
    processed_at: Optional[datetime]

class BillingServiceInterface(ABC):
    @abstractmethod
    def handle_webhook_event(self, event_data: Dict) -> WebhookResult:
        pass
```

### 3. Route Validation Pattern
```python
from pydantic import BaseModel, ValidationError
from app.schemas import ErrorEnvelope

class InventoryAdjustmentRequest(BaseModel):
    quantity: float
    change_type: str
    notes: Optional[str] = None

@inventory_bp.route('/adjust/<int:id>', methods=['POST'])
def adjust_inventory(id: int):
    try:
        # Parse & validate
        data = InventoryAdjustmentRequest.model_validate(request.json)

        # Service call
        result = inventory_service.adjust_inventory(id, data)

        # Response
        return jsonify(result)

    except ValidationError as e:
        return jsonify(ErrorEnvelope(
            error={"code": "VALIDATION_ERROR", "message": str(e), "details": e.errors()}
        )), 400
```

### 4. Performance Monitoring
```python
import time
import logging
from sqlalchemy import event

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute") 
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    if total > 0.1:  # Log queries >100ms
        logger.warning(f"Slow query ({total:.3f}s): {statement[:200]}...")
```

## CI/CD Pipeline Enhancement

### Quality Gates (All PRs)
- [ ] **pytest**: All tests must pass
- [ ] **ruff**: Code formatting and linting
- [ ] **mypy**: Type checking (informational initially)
- [ ] **bandit -q**: Security scanning (informational)

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
- [ ] **Query Counter**: Hot path executes ≤ N queries (fixture-based)
- [ ] **Response Time**: Critical endpoints respond in <200ms
- [ ] **Memory Usage**: No obvious memory leaks in service calls

### Security Tests
- [ ] **CSRF**: Forms reject requests without valid tokens
- [ ] **Rate Limiting**: Auth endpoints properly throttle
- [ ] **Headers**: Security headers present in responses

## Migration from Current State

### Phase 2 Complete Prerequisites
- ✅ Canonical inventory service (`process_inventory_adjustment`) stable
- ✅ All inventory changes flow through canonical service
- ✅ Test suite: 24/24 tests passing
- ✅ Legacy shims removed, business logic out of routes

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

**Target**: Production-ready codebase with enterprise-grade quality, security, and performance characteristics.