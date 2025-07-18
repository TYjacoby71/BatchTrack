
# Database Models & Relationships

**Complete guide to BatchTrack's database architecture**

## Core Models

### User
- **Purpose**: System users across all types
- **Scoping**: `organization_id` (nullable for developers)
- **Key Fields**: `user_type`, `is_active`, `timezone`
- **Relationships**: Organization, UserRoleAssignment

### Organization
- **Purpose**: Multi-tenant isolation
- **Scoping**: Root level entity
- **Key Fields**: `subscription_tier`, `timezone`, `is_active`
- **Relationships**: Users, custom roles

### Role
- **Purpose**: Permission grouping
- **Scoping**: `organization_id` (nullable for system roles)
- **Key Fields**: `is_system_role`, `is_active`
- **Relationships**: Permissions (many-to-many), UserRoleAssignment

### Permission
- **Purpose**: Granular access control
- **Scoping**: Global (system-wide)
- **Key Fields**: `category`, `required_subscription_tier`
- **Relationships**: Roles (many-to-many)

### UserRoleAssignment
- **Purpose**: User-Role relationship tracking
- **Scoping**: `organization_id`
- **Key Fields**: `is_active`, `assigned_at`, `assigned_by`
- **Relationships**: User, Role, Assigner

## Production Models

### Recipe
- **Purpose**: Production formulas
- **Scoping**: `organization_id`
- **Key Fields**: `is_active`, `total_batch_cost`
- **Relationships**: RecipeIngredients, Batches

### RecipeIngredient
- **Purpose**: Recipe component specifications
- **Scoping**: Inherited from Recipe
- **Key Fields**: `quantity`, `unit_id`, `cost_per_unit`
- **Relationships**: Recipe, Ingredient, Unit

### Batch
- **Purpose**: Production run tracking
- **Scoping**: `organization_id`
- **Key Fields**: `status`, `started_at`, `finished_at`
- **Relationships**: Recipe, BatchIngredients, Products

### BatchIngredient
- **Purpose**: Actual ingredients used in batch
- **Scoping**: Inherited from Batch
- **Key Fields**: `quantity_used`, `lot_numbers`
- **Relationships**: Batch, Ingredient, InventoryItems

## Inventory Models

### Ingredient
- **Purpose**: Raw materials catalog
- **Scoping**: `organization_id`
- **Key Fields**: `density`, `category_id`, `is_active`
- **Relationships**: InventoryItems, Category

### InventoryItem
- **Purpose**: Stock tracking with FIFO
- **Scoping**: `organization_id`
- **Key Fields**: `quantity`, `cost_per_unit`, `expiration_date`
- **Relationships**: Ingredient, InventoryHistory

### InventoryHistory
- **Purpose**: All inventory movements
- **Scoping**: `organization_id`
- **Key Fields**: `change_type`, `quantity_change`, `reference_type`
- **Relationships**: InventoryItem, related records

### InventoryAdjustment
- **Purpose**: Manual stock corrections
- **Scoping**: `organization_id`
- **Key Fields**: `adjustment_type`, `reason`, `approved_by`
- **Relationships**: InventoryItems

## Product Models

### Product
- **Purpose**: Finished goods catalog
- **Scoping**: `organization_id`
- **Key Fields**: `name`, `description`, `is_active`
- **Relationships**: ProductSKU, ProductInventory

### ProductSKU
- **Purpose**: Sellable product variants
- **Scoping**: Inherited from Product
- **Key Fields**: `sku`, `price`, `weight`, `is_active`
- **Relationships**: Product, ProductInventory, Sales

### ProductInventory
- **Purpose**: Finished goods stock
- **Scoping**: `organization_id`
- **Key Fields**: `quantity`, `batch_id`, `expiration_date`
- **Relationships**: ProductSKU, Batch

## Support Models

### Unit
- **Purpose**: Measurement units (global)
- **Scoping**: System-wide
- **Key Fields**: `unit_type`, `symbol`, `conversion_factor`
- **Relationships**: RecipeIngredients, InventoryItems

### Category
- **Purpose**: Ingredient categorization
- **Scoping**: `organization_id`
- **Key Fields**: `name`, `color`, `is_active`
- **Relationships**: Ingredients

### UnitConversion
- **Purpose**: Unit conversion tracking
- **Scoping**: System-wide
- **Key Fields**: `from_unit_id`, `to_unit_id`, `conversion_factor`
- **Relationships**: Units

## Model Relationships

### Organization Hierarchy
```
Organization
├── Users (multiple)
├── Roles (custom only)
├── Recipes
├── Batches
├── Ingredients
├── Products
└── All scoped data
```

### User Management
```
User
├── Organization (belongs_to)
├── UserRoleAssignments (multiple)
└── Roles (through assignments)

Role
├── Permissions (many-to-many)
├── UserAssignments (multiple)
└── Users (through assignments)
```

### Production Flow
```
Recipe
├── RecipeIngredients
├── Batches (multiple)
└── Products (through batches)

Batch
├── Recipe (belongs_to)
├── BatchIngredients
└── ProductInventory (output)
```

### Inventory Management
```
Ingredient
├── InventoryItems (multiple lots)
├── InventoryHistory (all changes)
└── RecipeIngredients (usage)

InventoryItem
├── Ingredient (belongs_to)
├── History records
└── FIFO deductions
```

## Scoping Patterns

### ScopedModelMixin
```python
class ScopedModelMixin:
    organization_id = db.Column(db.Integer, 
                               db.ForeignKey('organization.id'), 
                               nullable=False)
    
    @classmethod
    def for_organization(cls, org_id):
        return cls.query.filter_by(organization_id=org_id)
```

### Developer Access Pattern
```python
# Developers can access any organization's data
if current_user.user_type == 'developer':
    selected_org = session.get('dev_selected_org_id')
    data = Model.for_organization(selected_org)
else:
    # Regular users see only their org
    data = Model.for_organization(current_user.organization_id)
```

## Migration Guidelines

### Adding New Models
1. Include `organization_id` for scoped models
2. Add appropriate indexes for performance
3. Include audit fields (`created_at`, `updated_at`)
4. Consider soft delete with `is_active`

### Modifying Existing Models
1. Use Alembic migrations for schema changes
2. Preserve data integrity with careful migrations
3. Update relationships and constraints
4. Test with sample data

### Data Integrity Rules
- Never orphan records (use foreign key constraints)
- Cascade deletes appropriately
- Maintain audit trails
- Respect organization scoping

## Performance Considerations

### Indexing Strategy
- `organization_id` on all scoped models
- Composite indexes for common queries
- Foreign key columns always indexed
- Date fields for time-based queries

### Query Optimization
- Always filter by `organization_id` first
- Use eager loading for related data
- Implement pagination for large datasets
- Cache frequently accessed reference data

### Database Maintenance
- Regular cleanup of old history records
- Archive completed batches periodically
- Monitor index usage and performance
- Implement data retention policies
