
# BatchTrack Repository Map - Refactor Analysis

## Tree Summary

### Key Directories by Size/Importance
```
app/
├── blueprints/        # 15+ feature modules (auth, billing, batches, inventory, etc.)
├── services/          # 15+ business logic services (billing, oauth, inventory, etc.)
├── models/           # 15+ database models
├── templates/        # 50+ Jinja2 templates organized by feature
├── static/js/        # Frontend JavaScript modules
├── routes/           # Additional route handlers
└── utils/            # Helper utilities

migrations/versions/  # 25+ Alembic migration files
docs/                # Comprehensive documentation
```

### Largest Files by LOC (Estimated)
- `app/blueprints/billing/routes.py` - Stripe integration, webhooks
- `app/services/billing_service.py` - Complex billing logic
- `app/models/models.py` - Core database models
- `app/blueprints/batches/routes.py` - Production batch management
- `app/services/inventory_adjustment.py` - Inventory business logic
- `app/blueprints/fifo/services.py` - FIFO inventory deduction
- `app/static/js/main.js` - Frontend application logic

## Critical Paths Analysis

### (a) Billing/Stripe Webhooks and API Usage
**Entry Points:**
- `app/blueprints/billing/routes.py` - Webhook handlers
- `app/services/stripe_service.py` - Stripe API wrapper
- `app/services/billing_service.py` - Business billing logic
- `app/services/offline_billing_service.py` - Offline billing fallback

**Risk Assessment:**
- Webhook signature verification present but needs verification
- Idempotency handling unclear - needs audit
- Multiple billing services suggest potential duplication

### (b) Auth (Google OAuth)
**Entry Points:**
- `app/blueprints/auth/routes.py` - OAuth flow handlers
- `app/services/oauth_service.py` - OAuth business logic
- `app/blueprints/auth/whop_auth.py` - Alternative auth provider

**Risk Assessment:**
- State/nonce verification needs audit
- CSRF protection implementation unclear
- Multiple auth methods increase complexity

### (c) Inventory/FIFO Adjustments and Stock Checks
**Entry Points:**
- `app/services/inventory_adjustment.py` - **SHOULD BE CANONICAL**
- `app/blueprints/fifo/services.py` - FIFO-specific logic
- `app/services/stock_check.py` - Availability validation
- `app/services/unit_conversion.py` - Unit conversions

**Risk Assessment:**
- **CRITICAL**: Multiple entry points to inventory changes detected
- FIFO service may be called directly from routes (bypassing canonical path)
- Unit conversion scattered across codebase

### (d) Product/Variant/SKU Management
**Entry Points:**
- `app/models/product.py` - Product data models
- `app/services/product_service.py` - Product business logic
- `app/blueprints/products/` - Product route handlers

**Risk Assessment:**
- Business logic may be scattered between routes and services
- SKU generation logic needs centralization

### (e) Shopify/Whop Entry Points
**Entry Points:**
- `app/services/whop_service.py` - Whop integration
- `app/services/pos_integration.py` - POS system integration
- Various webhook handlers for external integrations

**Risk Assessment:**
- External integrations may bypass central error handling
- Rate limiting not clearly implemented

## Hotspots Identified

### Long Functions & Business Logic in Routes
- Route handlers in `app/blueprints/*/routes.py` likely contain business logic
- View functions directly manipulating database sessions
- Repeated validation patterns across blueprints

### Duplicated Logic
- Multiple inventory adjustment paths
- Repeated permission checking patterns
- Unit conversion logic scattered
- Similar validation patterns across models

### N+1 Query Risks
- Organization-scoped queries without proper eager loading
- Batch-to-ingredient relationships
- Product-to-variant queries

### Global State & Configuration
- `current_app.config` accessed throughout codebase
- Flask session manipulation scattered
- No centralized request context management

### Missing Typing
- Service functions lack comprehensive type hints
- Model relationships not fully typed
- API response contracts not typed

## Tests Status

### Existing Tests
**Location Check:** `tests/` directory not visible in current structure

**Estimated Coverage:** Likely minimal based on typical Flask app patterns

### Missing Critical Tests
- Stripe webhook idempotency
- OAuth state/nonce validation
- FIFO inventory deduction accuracy
- Multi-tenant data isolation
- Permission system validation
- External integration error handling

## Immediate Risk List

### 🔴 High Priority Security Risks
1. **Webhook Idempotency** - Stripe webhooks may process duplicate events
2. **CSRF Protection** - Form submissions may lack CSRF validation
3. **OAuth State/Nonce** - State parameter validation needs verification
4. **Rate Limiting** - Auth endpoints and webhooks lack rate protection

### 🟡 Medium Priority Data Risks
5. **Migration Drift** - Multiple migration files suggest potential conflicts
6. **Inventory Consistency** - Multiple entry points risk data corruption
7. **Organization Scoping** - Multi-tenant queries may have isolation bugs

### 🟢 Low Priority Technical Debt
8. **Configuration Management** - Scattered config access
9. **Error Handling** - Inconsistent error responses
10. **Code Duplication** - Repeated patterns across modules

## Refactor Strategy Recommendations

### Phase 1: Safety First
1. Implement comprehensive characterization tests
2. Add CI/CD pipeline with quality gates
3. Audit and fix security vulnerabilities

### Phase 2: Structural Cleanup
1. **Mandate single inventory entry point** through `inventory_adjustment.py`
2. Move business logic out of route handlers
3. Centralize external service calls

### Phase 3: Consistency & Performance
1. Eliminate code duplication
2. Add comprehensive typing
3. Optimize database queries
4. Standardize error handling

## Architecture Decision Record Topics
- Single inventory adjustment entry point
- External service integration patterns
- Request context and logging strategy
- Multi-tenant data isolation patterns
- Error handling and response standardization

---

**Next Steps:** Await approval to proceed with Step 1 - Guardrails & CI implementation.

**Estimated Refactor Timeline:** 3-4 weeks with proper testing and review cycles.
