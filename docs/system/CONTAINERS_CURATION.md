## Global Containers Curation Guide

This guide defines how to curate and load container records into the Global Item Library so organizations can adopt standardized, searchable containers.

### Core model fields (GlobalItem, item_type='container')
- name: Human name of the container (short, canonical). Example: "Straight Sided Jar"
- item_type: Must be "container"
- capacity: Numeric storage capacity per container (e.g., 8.0)
- capacity_unit: Unit name (e.g., "fl oz", "oz", "ml", "g")
- container_material: Material of the container (e.g., "Glass", "PET Plastic", "Aluminum")
- container_type: Base type (e.g., "Jar", "Bottle", "Tin", "Tube", "Glass")
- container_style: Optional style/subtype (e.g., "Boston Round", "Straight Sided", "Drinking")
- container_color: Optional color (e.g., "Amber", "Clear", "White")
- default_unit: Optional; generally not used for containers (containers are tracked as count). Leave null.
- aka_names: Optional list of synonyms

Notes
- Capacity and capacity_unit should reflect the typical advertised size for that container item (per piece).
- Color is useful for e-commerce mappings and differentiation (e.g., Amber vs Clear).
- Name should be generic and not include capacity, color, or material redundancies; those are stored structurally.

### Naming rules and redundancy avoidance
- Do not bake capacity or unit into `name` (capacity is a separate field).
- Avoid repeating material in both `container_type` and `container_material`.
  - Example: Use container_type="Glass" and container_style="Drinking" for a drinking glass. The display logic will render "Drinking Glass" without duplicating "Glass".

### Runtime container naming
- The application never trusts free-form input for container names. All creation and edit flows call `app/services/container_name_builder.py`.
- `build_container_name()` accepts the structured attributes (style, material, base type, color, capacity, unit) and returns a canonical descriptor such as `Amber Boston Round Glass Bottle - 8 fl oz`.
- Any new workflow that needs a container label must import and call that helper instead of rolling its own formatting logic. This prevents "competing services" that might drift out of sync.

### JSON schema (informal)
```json
{
  "items": [
    {
      "name": "Straight Sided Jar",
      "item_type": "container",
      "capacity": 8.0,
      "capacity_unit": "fl oz",
      "container_material": "Glass",
      "container_type": "Jar",
      "container_style": "Straight Sided",
      "container_color": "Clear",
      "aka_names": ["Straight-Sided Jar"]
    }
  ]
}
```

### CSV header format
Required columns for CSV import:
```
name,capacity,capacity_unit,container_material,container_type,container_style,container_color
```
Optional columns:
```
aka_names (semicolon-separated),default_unit
```

### Examples
- 8 fl oz Straight Sided Glass Jar (Clear)
  - name: Straight Sided Jar
  - capacity: 8.0
  - capacity_unit: fl oz
  - container_material: Glass
  - container_type: Jar
  - container_style: Straight Sided
  - container_color: Clear

- 4 oz Boston Round Glass Bottle (Amber)
  - name: Boston Round Bottle
  - capacity: 4.0
  - capacity_unit: oz
  - container_material: Glass
  - container_type: Bottle
  - container_style: Boston Round
  - container_color: Amber

### Deduplication guidance
- Treat (name, capacity, capacity_unit, container_material, container_type, container_style, container_color) as the uniqueness signature for a curated record. If only color differs, separate records are acceptable.
- Inventory creation reuses this exact signature through `_find_matching_container()` inside `app/services/inventory_adjustment/_creation_logic.py`, so repeated submissions with identical attributes re-link to the same `InventoryItem` even if the user re-enters it later.

### Loading curated data
- Use `scripts/seed_containers.py` to upsert curated JSON/CSV into `GlobalItem`.
- JSON can be either an array of items or an object with an `items` array.
- CSV must use the header format described above.

### QA checklist per item
- Capacity value is numeric and positive
- Capacity unit is present and standard
- Name is short and generic (no capacity embedded)
- Material/Type/Style/Color properly assigned
- No material duplication between type/style and material

