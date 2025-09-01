
# Naming Standardization Plan

## Current Inconsistencies Analysis

### URL Patterns
- ❌ Mixed: `/recipes/` vs `/production-planning/<id>/plan`
- ❌ Inconsistent: Some use `/` for list, others `/list`
- ❌ Random: `/recipe/5/edit` vs `/recipes/5/plan`

### Function Names
- ❌ Mixed: `list_recipes` vs `plan_production` vs `view_recipe`
- ❌ Inconsistent: `recipe_list` vs `list_recipes`

### Template Names
- ❌ Mixed: `recipe_list.html` vs function `list_recipes`

## Standardization Rules

### 1. URL Patterns
```
LIST:     /<blueprint>/                    # /recipes/, /products/, /batches/
VIEW:     /<blueprint>/<id>                # /recipes/5, /products/10
EDIT:     /<blueprint>/<id>/edit           # /recipes/5/edit
CREATE:   /<blueprint>/new                 # /recipes/new
DELETE:   /<blueprint>/<id>/delete         # /recipes/5/delete
ACTION:   /<blueprint>/<id>/<action>       # /recipes/5/duplicate
```

### 2. Function Names
```
LIST:     list_<resource>                  # list_recipes, list_products
VIEW:     view_<resource>                  # view_recipe, view_product  
EDIT:     edit_<resource>                  # edit_recipe, edit_product
CREATE:   create_<resource>                # create_recipe, create_product
DELETE:   delete_<resource>                # delete_recipe, delete_product
ACTION:   <action>_<resource>              # duplicate_recipe, archive_product
```

### 3. Template Names
```
LIST:     list_<resource>.html             # list_recipes.html
VIEW:     view_<resource>.html             # view_recipe.html
EDIT:     edit_<resource>.html             # edit_recipe.html
CREATE:   create_<resource>.html           # create_recipe.html
```

## Blueprint-by-Blueprint Refactoring

### Phase 1: Core Blueprints
1. **Recipes** - Fix inconsistencies
2. **Products** - Standardize patterns
3. **Inventory** - Align with standards
4. **Batches** - Standardize naming

### Phase 2: Secondary Blueprints
5. **Production Planning** - Keep separate, standardize internally
6. **Organization** - Fix patterns
7. **Settings** - Align conventions

### Phase 3: API & Admin
8. **API routes** - Standardize endpoints
9. **Admin routes** - Fix inconsistencies

## Production Planning Exception

Production planning remains its own blueprint with standardized internal patterns:
```
URL:      /production-planning/<recipe_id>/plan
Function: plan_production  
Template: plan_production.html
```

## Implementation Strategy

1. **Create URL mapping document** - Map all current routes
2. **Update one blueprint at a time** - Start with recipes
3. **Update all URL references** - Templates, JavaScript, redirects
4. **Test each phase** - Ensure no broken links
5. **Update documentation** - Reflect new patterns

## Breaking Changes

### Templates Need Updates
- All `url_for()` calls need blueprint.function updates
- JavaScript fetch URLs need updates
- Breadcrumb navigation needs updates

### JavaScript Updates  
- API endpoint URLs need updates
- Form submission URLs need updates
- Navigation links need updates

## Success Metrics

- ✅ All URLs follow consistent pattern
- ✅ All function names follow convention
- ✅ All templates named consistently  
- ✅ No broken links or 404s
- ✅ JavaScript API calls work
- ✅ All tests pass

## Timeline

- **Week 1**: Recipes + Products blueprints
- **Week 2**: Inventory + Batches blueprints  
- **Week 3**: Production Planning + Organization
- **Week 4**: API routes + final testing
