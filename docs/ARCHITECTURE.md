
# BatchTrack Architecture Guide

## System Overview

BatchTrack is a multi-tenant SaaS application built on a service-oriented architecture where each service has authoritative control over its domain. The system is designed to scale from single-user installations to multi-tenant SaaS with thousands of organizations.

## Core Principles

### 1. Service Authority
Each service is the **single source of truth** for its domain:
- **FIFO Service** (`app/blueprints/fifo/services.py`) - Controls inventory deduction order
- **Inventory Adjustment Service** (`app/services/inventory_adjustment.py`) - All inventory changes
- **Unit Conversion Service** (`app/services/unit_conversion.py`) - All unit conversions
- **Stock Check Service** (`app/services/stock_check.py`) - Availability validation
- **Expiration Service** (`app/blueprints/expiration/services.py`) - Shelf-life management

### 2. Multi-Tenant Data Scoping
- All data is scoped by `organization_id`
- Developers (`user_type = 'developer'`) have no `organization_id` and system-wide access
- Organization owners manage their own data and team members
- Subscription tiers control available features and user limits

### 3. Permission-Based Access
- Roles are collections of permissions
- Permissions are atomic actions (`inventory.adjust`, `batch.start`, etc.)
- No hardcoded role checks - always use `has_permission(user, permission_name)`

## Data Flow Architecture

### Batch Production Flow
```
Recipe → Plan Production → Start Batch → Batch In Progress → Finish Batch → Products
   ↓           ↓              ↓              ↓               ↓
Stock Check → Reserve → Deduct (FIFO) → Track Progress → Add Products
```

### Inventory Management Flow
```
Restock → Inventory Adjustment Service → FIFO Service → Inventory History
   ↓                    ↓                     ↓              ↓
Cost Tracking → Apply Change → Update Lots → Log Change
```

### User Management Flow
```
Organization Owner → Create Roles → Assign Permissions → Invite Users → Assign Roles
        ↓                ↓              ↓               ↓           ↓
Subscription Tier → Available Features → User Limits → Team Members → Access Control
```

## Service Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                        Controllers                               │
├─────────────────────────────────────────────────────────────────┤
│                     Business Logic                              │
├─────────────────────────────────────────────────────────────────┤
│  FIFO Service  │ Inventory Service │ Conversion │ Stock Check   │
├─────────────────────────────────────────────────────────────────┤
│                      Data Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│                     Database                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Security & Scoping

### Organization Isolation
- Database queries automatically filter by `organization_id`
- Cross-organization data access is impossible for non-developers
- Each organization has isolated roles, permissions, and data

### Permission Inheritance
- Organization owners can create custom roles
- Default system roles provided by developers
- Subscription tiers limit available permissions

## Error Handling & Validation

### Service-Level Validation
- Each service validates its own domain rules
- Cross-service validation happens at the business logic layer
- Database constraints provide final safety net

### Graceful Degradation
- Stock checks fail-safe (show warnings, don't block)
- FIFO deduction attempts to find available inventory
- Unit conversions fall back to base units

## Performance Considerations

### Database Optimization
- Indexes on `organization_id` for multi-tenant queries
- FIFO queries optimized for batch lot ordering
- Inventory history partitioned by organization

### Caching Strategy
- Unit conversion cache for repeated calculations
- Stock check cache for production planning
- Permission cache for user sessions

## Monitoring & Observability

### Logging
- Service-level logging for all major operations
- Inventory adjustment audit trail
- FIFO deduction tracking
- Permission check logging

### Metrics
- Batch production times
- Inventory accuracy
- User activity patterns
- System performance metrics

## Development Guidelines

### Adding New Features
1. Identify which service owns the functionality
2. Add business logic to appropriate service
3. Create controller endpoints that use services
4. Add proper permission checks
5. Update documentation

### Modifying Existing Features
1. Check service authority - don't bypass services
2. Maintain organization scoping
3. Preserve audit trails
4. Test multi-tenant scenarios
5. Update related documentation

### Database Changes
1. Use Alembic migrations
2. Consider multi-tenant implications
3. Maintain foreign key relationships
4. Add appropriate indexes
5. Test with large datasets

## Testing Strategy

### Unit Tests
- Service-level functionality
- Permission validation
- Unit conversion accuracy
- FIFO deduction logic

### Integration Tests
- Full batch production flow
- Multi-tenant data isolation
- Permission inheritance
- Cross-service interactions

### Performance Tests
- Large inventory datasets
- Multiple organizations
- Concurrent user scenarios
- Database query performance

---

**Next:** See [SERVICES.md](SERVICES.md) for detailed service specifications.
