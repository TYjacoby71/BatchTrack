# Container Architecture Analysis

## Current Architecture ✅ CORRECT

### Data Model
1. **GlobalItem** - Global library of items (containers, ingredients, etc.) shared across all organizations
2. **InventoryItem** - Organization-specific inventory that can either:
   - Link to a GlobalItem (via `global_item_id`) with `ownership='global'`
   - Be a custom org-specific item with `ownership='org'`

### Container Storage in Recipes
- `Recipe.allowed_containers` stores a list of **InventoryItem.id** values (NOT GlobalItem.id)
- These IDs are organization-scoped, so each organization has its own InventoryItem records
- When an organization adds a container from the global library, it creates an InventoryItem record with:
  - `global_item_id` pointing to the GlobalItem
  - `organization_id` set to their organization
  - `ownership='global'`

### Container Loading Flow

#### 1. Recipe Form (Container Selection)
**File:** `app/blueprints/recipes/routes.py` - `_get_recipe_form_data()`
```python
ingredients_query = InventoryItem.query.filter(
    ~InventoryItem.type.in_(['product', 'product-reserved'])
).order_by(InventoryItem.name)

if current_user.organization_id:
    ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)
```
✅ **Correct**: Filters by organization_id, only shows containers belonging to current org

#### 2. Production Planning (Container Usage)
**File:** `app/services/production_planning/_container_management.py` - `_load_suitable_containers()`
```python
allowed_container_ids = getattr(recipe, 'allowed_containers', [])

containers = InventoryItem.query.filter(
    InventoryItem.id.in_(allowed_container_ids),
    InventoryItem.organization_id == org_id,
    InventoryItem.quantity > 0
).all()
```
✅ **Correct**: 
- Uses the stored InventoryItem IDs from recipe
- Filters by organization_id for security
- Only shows containers with quantity > 0

#### 3. Finish Batch (SKU Creation)
**File:** `app/blueprints/batches/finish_batch.py` - `_create_container_sku()`
```python
# Uses container_display_name to build size_label
if container_item.capacity and container_item.capacity_unit:
    cap_str = f"{container_item.capacity} {container_item.capacity_unit}".strip()
    display_name = container_item.container_display_name
    size_label = f"{cap_str} {display_name}".strip()
```
✅ **Correct**: Already using container_display_name

### Container Display Name Property

**File:** `app/models/inventory.py` - `InventoryItem.container_display_name`

The property constructs a clean display name from structured attributes:
```python
@property
def container_display_name(self):
    """Derived clean display name for containers from structured attributes.
    
    Rules:
    - Prefer style first if present (e.g., "Boston Round", "Straight Sided")
    - Append material only if not already in style or type
    - Always include the base type (e.g., "Jar", "Bottle")
    """
    if self.type != 'container':
        return self.name
    
    style = (self.container_style or '').strip()
    material = (self.container_material or '').strip()
    base_type = (self.container_shape or '').strip()
    
    parts = []
    if style:
        parts.append(style)
    
    # Add material only if not duplicated
    if material and not (material.lower() in style.lower() or material.lower() in base_type.lower()):
        parts.append(material)
    
    if base_type:
        parts.append(base_type)
    
    return " ".join([p for p in parts if p]).strip() or self.name
```

**Examples:**
- style="Boston Round", material="Glass", shape="Bottle" → "Boston Round Glass Bottle"
- style="Boston Round Glass", material="Glass", shape="Bottle" → "Boston Round Glass Bottle" (no duplication)
- style="", material="Plastic", shape="Jar" → "Plastic Jar"

## Issues Fixed

### 1. Recipe Form Display ✅ FIXED
**File:** `app/templates/pages/recipes/recipe_form.html` (line 391)
- **Before:** `{{ container.name }}`
- **After:** `{{ container.container_display_name }}`
- **Impact:** Users now see properly formatted container names when selecting containers for recipes

### 2. Already Fixed in Previous Updates
All backend systems already updated to use `container_display_name`:
- Production planning container management
- Stock check handlers
- Batch operations
- API responses
- SKU creation

## SKU Name Builder Tokens

**File:** `app/services/sku_name_builder.py`

Available tokens for SKU naming templates:
```python
values = {
    'product': context.get('product'),
    'variant': context.get('variant'),
    'container': context.get('container'),  # ← Receives the full container display name
    'size_label': context.get('size_label'),
    'yield_value': context.get('yield_value'),
    'yield_unit': context.get('yield_unit'),
    'portion_name': context.get('portion_name'),
    'portion_count': context.get('portion_count'),
    'portion_size_value': context.get('portion_size_value'),
    'portion_size_unit': context.get('portion_size_unit'),
}
```

### Current Container Token Usage
The `{container}` token receives the complete `size_label` which includes:
- Capacity + Capacity Unit + Container Display Name
- Example: "8 fl oz Boston Round Glass Bottle"

### Potential Enhancement: Granular Container Tokens

If you want more control over container naming in SKU templates, you could add additional tokens:

**Suggested New Tokens:**
```python
'container_full': '8 fl oz Boston Round Glass Bottle',    # Current {container}
'container_name': 'Boston Round Glass Bottle',             # Display name only
'container_style': 'Boston Round',                         # Style only
'container_material': 'Glass',                             # Material only
'container_shape': 'Bottle',                               # Shape/type only
'container_capacity': '8',                                 # Capacity value
'container_capacity_unit': 'fl oz',                        # Capacity unit
```

This would allow templates like:
- `{variant} {product} in {container_style} {container_shape}` → "Lavender Lotion in Boston Round Bottle"
- `{product} {variant} ({container_capacity} {container_capacity_unit})` → "Lotion Lavender (8 fl oz)"

## Recommendations

### Current State: ✅ Working Correctly
The architecture is sound:
1. Container IDs are organization-scoped (InventoryItem.id)
2. Global containers create org-specific InventoryItem records
3. Recipe allowed_containers stores org-scoped IDs
4. All queries filter by organization_id for security
5. Container display names now used throughout the system

### Optional Enhancement: Granular SKU Tokens
If you need more flexibility in SKU naming, consider adding the granular container tokens listed above. This would require:

1. **Update `_create_container_sku` in `finish_batch.py`:**
```python
naming_context = {
    'container': size_label,  # Full format (current)
    'container_name': display_name,  # Name only
    'container_style': container_item.container_style or '',
    'container_material': container_item.container_material or '',
    'container_shape': container_item.container_shape or '',
    'container_capacity': str(container_item.capacity or ''),
    'container_capacity_unit': container_item.capacity_unit or '',
    'yield_value': batch.final_quantity,
    'yield_unit': batch.output_unit,
}
```

2. **Update `SKUNameBuilder.render()` to include new tokens**

3. **Update documentation to show available tokens**

## Conclusion

✅ The container architecture is **correctly implemented**
✅ Container IDs are **organization-scoped** 
✅ Display names now **used throughout the system**
✅ No issues with global vs org container mixing

The system properly handles both:
- Containers linked to the global library (with org-specific InventoryItem records)
- Custom org-specific containers

All security and scoping concerns are properly addressed.
