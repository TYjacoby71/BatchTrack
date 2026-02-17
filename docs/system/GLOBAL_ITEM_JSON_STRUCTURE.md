# Global Item JSON Structure Guide

## Synopsis
This guide defines the current JSON layout used to seed the platform global inventory library (ingredients, containers, packaging, consumables). It reflects the active `app/seeders/globallist/` structure and the seeding pipeline used by the app CLI.

## Glossary
- **Category file**: One JSON document containing category metadata and an `items` array.
- **Global item seed**: A row candidate for `GlobalItem`, including optional domain metadata.
- **Seed pipeline**: The import flow that reads `globallist` files and writes/updates model records.

## Directory Layout

```text
app/seeders/globallist/
├── ingredients/categories/
├── containers/categories/
├── packaging/categories/
└── consumables/categories/
```

## Category-Level Schema (Root Object)

All category files should include:

```json
{
  "category_name": "Glass Containers",
  "description": "Category description",
  "items": []
}
```

Common optional category fields:
- `material` (commonly used by container/packaging/consumable files)
- `default_capacity_unit` (for container-like categories)
- `default_density` (used by ingredient categories)

## Item-Level Schema (Items Array)

All item rows should include:
- `name` (string)

Common optional fields used across domains:
- `aliases` or `aka_names` (synonyms)
- `default_unit`
- `density`
- `recommended_shelf_life_days`
- `inci_name`
- `certifications`

### Container/Packaging/Consumable-Oriented Fields
- `capacity`
- `capacity_unit`
- `container_type`
- `container_style`
- `container_color`

### Ingredient-Oriented Extended Fields
Ingredient category files may include richer metadata used by formulation and catalog UX, for example:
- `saponification_value`
- `iodine_value`
- `fatty_acid_profile`
- `is_active_ingredient`
- nested ingredient identity blocks (for slug/INCI normalization)

## Validation and Authoring Notes
- Keep item names deterministic and human-readable.
- Prefer standard units (`oz`, `fl oz`, `ml`, `count`, etc.).
- Keep optional metadata sparse but accurate; omit unknown fields instead of guessing values.
- Preserve JSON validity and avoid trailing comments (JSON does not allow comments).

## Seeding Commands (Current)

Preferred app CLI command:

```bash
flask seed-global-inventory
```

Direct script execution (from repo root):

```bash
python app/seeders/seed_global_inventory_library.py
```

## Relevance Check (2026-02-17)
Verified against:
- `app/seeders/seed_global_inventory_library.py`
- `app/scripts/commands/seeding.py` (`seed-global-inventory`)
- `app/seeders/globallist/**/categories/*.json`
