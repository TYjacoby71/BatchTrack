
# Global Item JSON Structure Guide

This document explains the JSON structure for seeding global items across different categories.

## File Organization

Global item seed files are organized by type and material:

```
app/seeders/globallist/
├── ingredients/categories/          # Ingredient categories (existing)
├── containers/categories/           # Container categories by material
├── packaging/categories/            # Packaging categories by material
└── consumables/categories/          # Consumable categories by function
```

## JSON Structure

### Category Level (Root Object)

```json
{
  "category_name": "Glass Containers",
  "material": "Glass",                    // Primary material
  "default_capacity_unit": "oz",          // Default unit for this category
  "description": "Description of category",
  "item_type": "container",               // Auto-added by seeder
  "items": [...]                          // Array of items
}
```

### Item Level (Items Array)

```json
{
  "name": "Straight Sided Jar",
  "capacity": 8.0,                        // Numeric capacity
  "capacity_unit": "fl oz",               // Unit for this specific item
  "container_type": "Jar",                // Type: Jar, Bottle, Tin, etc.
  "container_style": "Straight Sided",    // Style/subtype
  "container_color": "Clear",             // Color (can be null)
  "aka_names": ["Alternative Name"],      // Array of synonyms
  "density_g_per_ml": 0.95,              // Optional density
  "default_unit": "count",                // Optional default unit
  "perishable": false,                    // Optional perishable flag
  "shelf_life_days": 365                  // Optional shelf life
}
```

## Required Fields by Item Type

### Containers
- `name` (string)
- `capacity` (number)
- `capacity_unit` (string)
- `container_type` (string)

### Packaging
- `name` (string)
- `capacity` (number, often 1.0 for count-based items)
- `capacity_unit` (string, often "count")
- `container_type` (string)

### Consumables
- `name` (string)
- `capacity` (number)
- `capacity_unit` (string)
- `container_type` (string)

### Ingredients
- `name` (string)
- `density_g_per_ml` (number)

## Material Categories

### Containers
- `glass.json` - Glass containers
- `plastic_pet.json` - PET plastic containers
- `plastic_hdpe.json` - HDPE plastic containers
- `aluminum.json` - Aluminum containers
- `tin_steel.json` - Tin and steel containers

### Packaging
- `boxes_cardboard.json` - Cardboard packaging
- `bags_pouches.json` - Flexible packaging
- `labels_stickers.json` - Labels and adhesive materials

### Consumables
- `tools_supplies.json` - Manufacturing tools and supplies
- `cleaning_materials.json` - Cleaning and sanitization materials

## Usage

1. Create JSON files following the structure above
2. Place them in the appropriate category directory
3. Run the seeder script:

```bash
python scripts/seed_global_items_from_density_reference.py
```

The seeder will automatically detect the item type based on the directory structure and populate the global items library accordingly.
