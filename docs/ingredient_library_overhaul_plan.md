# Ingredient Library Overhaul – Schema & Migration Plan

## Objectives
- **Normalize library data** into two layers: `ingredient` (abstract concept) and `ingredient_item` (physical form/SKU).
- **Introduce flexible attributes** stored as JSON blobs keyed by domain (soap, brewing, baking, etc.).
- **Replace rigid category toggles** with hierarchical taxonomies/tagging that can grow without schema churn.
- **Preserve existing inventory links** by backfilling new references and migrating data from `global_item`.

## Target Schema (ERD Overview)

```
Ingredient (new)
  ├─ ingredient_id (PK, string)
  ├─ name, inci_name, cas_number, description
  ├─ aliases (JSON array)
  ├─ is_active_ingredient (bool)
  ├─ taxonomy summary cache (JSON, optional)
  └─ timestamps

IngredientItem (new)
  ├─ item_id (PK, string)
  ├─ ingredient_id (FK → Ingredient)
  ├─ physical_form (enum/text)
  ├─ default_unit
  ├─ density_g_ml, shelf_life_days
  ├─ ph_min, ph_max, ph_display
  ├─ attributes (JSONB)  # keyed sub-objects: soap, brewing, baking, etc.
  ├─ certifications (JSON array)
  ├─ suppliers (JSON array, optional future use)
  ├─ metadata (JSON: seed source, notes)
  └─ timestamps

IngredientTag (new)
  ├─ id (PK)
  ├─ taxonomy (enum: ingredient_category, application, function, dietary, etc.)
  ├─ slug, name, parent_id (self FK for hierarchy)
  └─ metadata/timestamps

IngredientTagLink (new)
  ├─ id (PK)
  ├─ ingredient_id (FK)           # tags apply at ingredient level
  ├─ tag_id (FK → IngredientTag)
  └─ timestamps

InventoryItem (existing)
  ├─ Add column `ingredient_item_id` (FK → IngredientItem, nullable during migration)
  ├─ Add column `attributes` (JSON) to store per-org overrides
  ├─ Deprecate direct columns: `saponification_value`, `protein_content_pct`, etc. (leave for compatibility, mark legacy)
```

### Relationships
- `Ingredient` 1─* `IngredientItem`
- `Ingredient` *─* `IngredientTag` via `IngredientTagLink`
- `InventoryItem` *─1 `IngredientItem`
- Existing tables referencing `global_item` (e.g. recipes, suggestions) will point into `IngredientItem` post-migration.

## Migration Strategy

1. **Phase A – Schema Preparation**
   - Create new tables: `ingredient`, `ingredient_item`, `ingredient_tag`, `ingredient_tag_link`.
   - Add staging columns to `inventory_item`, `recipe_ingredient`, `inventory_item.global_item_id` replacements, etc.
   - Keep legacy `global_item` table untouched during build-out for safety.

2. **Phase B – Data Backfill**
   1. Seed canonical `Ingredient` and `IngredientItem` from existing `global_item` rows.
      - Derive deterministic IDs (e.g., `BOT-BAS-001` for ingredient, `BOT-BAS-001-POW` for item) based on category + slug + physical form.
      - Collapse duplicates: group by normalized name + physical form synonyms (`whole`, `powder`, etc.).
   2. Populate `IngredientTag` tree from current `ingredient_category` and other metadata.
      - Example: convert `ingredient_category.name` → `ingredient_category` taxonomy.
      - Add `application`/`function` tags from curated JSON lists.
   3. Link existing `global_item` aliases → `Ingredient` (`aliases` JSON).
   4. Attach tags via `IngredientTagLink`.
   5. Update `inventory_item` records:
      - Map existing `global_item_id` to new `ingredient_item_id`.
      - Move extended attributes (soap/brewing/etc.) into `inventory_item.attributes`.
      - Retain legacy columns during transition (filled from JSON for backwards compatibility).
   6. Update dependent tables (recipes, suggestions, statistics) to reference new IDs.

3. **Phase C – Cutover**
   - Swap application code to use new tables.
   - Enforce non-null constraints on `inventory_item.ingredient_item_id`.
   - Deprecate/rename `global_item` (either drop, archive, or keep as view).

4. **Phase D – Cleanup**
   - Remove obsolete columns (`recommended_usage_rate`, etc.) once all consumers read from JSON.
   - Drop legacy category toggle columns.
   - Ensure indexes/query plans exist for new tag tables (`GIN` on attributes, b-tree on tag joins).

## Data Flow Details

- **Physical Form Consolidation**
  - Normalize terms (`Whole Leaf`, `Powder`, `Cut & Sifted`, etc.) into controlled vocabulary stored in `ingredient_physical_form` lookup or enumerated config.
  - Map synonyms via migration (e.g., `Whole Pod`, `Whole` → `whole`).

- **Attribute JSON Structure**
  ```json
  {
    "soap": {
      "saponification_value": 0.128,
      "iodine_value": 65,
      "comedogenic_rating": 0
    },
    "cosmetics": {
      "recommended_usage_rate": "0.5-2%"
    },
    "brewing": {
      "color_srm": 9.5,
      "potential_sg": 1.036
    },
    "food": {
      "protein_content_pct": 12.5
    }
  }
  ```

- **Inventory Item Overrides**
  - When an organization edits density or usage rates, store in `inventory_item.attributes` with same structure.
  - At runtime, merge org overrides over ingredient defaults.

## SQL Migration Rough Order

1. `alembic revision --autogenerate` skeleton for new tables.
2. Manual edits:
   ```sql
   CREATE TABLE ingredient (...);
   CREATE TABLE ingredient_item (... references ingredient ...);
   CREATE TABLE ingredient_tag (... self FK ...);
   CREATE TABLE ingredient_tag_link (... references ingredient, ingredient_tag ...);

   ALTER TABLE inventory_item
     ADD COLUMN ingredient_item_id VARCHAR(32),
     ADD COLUMN attributes JSONB;
   CREATE INDEX ix_inventory_item_ingredient_item_id ON inventory_item (ingredient_item_id);
   ```
3. Backfill migration (separate revision):
   - Use Python script to transform `global_item` data (respecting transaction batches).
   - Temporary mapping table: `global_item_to_ingredient_item` storing old → new IDs to help updates.
4. Follow-up migration to enforce constraints and drop unused columns once application updated.

## Open Questions / Decisions Needed
- **ID format**: string vs numeric? Proposal: use short slug-based strings for readability, stored as PK (e.g., `BOT-BAS-001-POW`). Alternatively, use UUIDs with separate slug column.
- **Taxonomy management UI**: fold into existing admin pages or new blueprint?
- **Backward compatibility period**: how long to keep `global_item` accessible (read-only) for legacy API consumers?
- **Search indexing**: ensure new tag-based filters integrate with existing search services (`InventorySearchService`, `GlobalItemStatsService`).

## Next Steps
1. Finalize ID strategy and physical form vocabulary.
2. Approve schema & migration phases.
3. Proceed with migration implementation (`task-2`).
