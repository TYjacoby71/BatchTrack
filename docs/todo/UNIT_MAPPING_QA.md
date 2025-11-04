
# ✅ Custom Unit & Mapping QA and Validation Rules

This document outlines the logic, guardrails, validation flow, and UX feedback required to maintain consistency, clarity, and accuracy within BatchTrack's custom unit and mapping system.

---

## 🔧 1. System Definitions

| Object | Definition |
|--------|------------|
| **Unit** | A measure used in recipes and inventory. Can be weight (g), volume (ml), count, length, or area. Custom units are allowed. |
| **Container** | An inventory item that stores a defined amount of another unit (e.g., jar holds 4oz). Not used for unit logic — only for packaging and labeling. |
| **Custom Unit** | A user-defined unit (e.g., "scoop", "bucket", "dab") created to represent intuitive measurement. Requires mapping to known unit. |
| **Custom Mapping** | A record that defines how a custom unit translates to a known unit and resolves to base. Example: `1 scoop = 4 grams` |
| **Density** | An ingredient-level property that enables conversion between volume and weight. |

---

## 🧪 2. Guardrails & Validation

### ✅ On Custom Mapping Creation
- ✅ Must prevent cross-type mapping **except**:
  - Volume ↔ Weight → ✅ Allowed only if a density is known or user is defining one
  - Length ↔ Area → ❌ Disallowed unless future functionality is added
- ✅ Disallow Count ↔ Volume or Count ↔ Weight mappings — only Count ↔ Count is valid
- ✅ If mapping is cross-type (e.g., 1 bucket → 1 lb):
  - Check if ingredient context is known
  - If yes, suggest assigning density
  - If no, allow saving but flag unit as "cross-mapped" with no density

### ✅ On Unit Usage in Recipes
- ✅ If a unit is used in a recipe and is:
  - Custom
  - Not a `count`
  - Has **no valid mapping**
  
  → ❌ **BLOCK** recipe from passing stock check
  → ✅ Show message: "This recipe uses a custom unit (e.g., 'bucket') that is not mapped to a known unit. Go to the Unit Manager to define a custom mapping."

### ✅ On Stock Check
- ✅ If a custom unit has a cross-type mapping (e.g., volume → weight) and the ingredient:
  - ❌ Does NOT have a density defined

  → BLOCK stock check with message:
  "This recipe uses a unit conversion that requires density. The ingredient 'Rocks' must have a defined density to convert 'bucket' to 'lb'. Set this in the Inventory Manager."

---

## 🧠 3. UX Recommendations

### ✅ Unit Manager Enhancements
- ✅ Display status for custom units:
  - "Unmapped"
  - "Mapped to weight via lb"
  - "Cross-type mapping pending density"

### ✅ Recipe Editor Enhancements
- ✅ Show alert when an unmapped custom unit is selected in the recipe
- ✅ Suggest available mappings when unit is used

### ✅ Mapping Creation Form
- ✅ Add instructions:
  > "Define how your custom unit relates to a known unit. For example, if '1 scoop = 10 grams', choose 'scoop' as the custom unit and 'gram' as the known unit, with a multiplier of 10."
- ✅ Add "Advanced Options" collapsible with:
  - Training video link
  - Density explanation
  - Real-world examples (e.g., ladles of soup, buckets of gravel)

---

## 🧱 4. Developer Notes

- ✅ Add flag to Unit model: `is_mapped: bool`
- ✅ If unit is custom and `is_mapped = False`, block all recipe and stock logic
- ✅ Only allow cross-type mapping if:
  - From + To type is volume/weight
  - Ingredient has density OR prompt for it

- ✅ Never allow custom mapping to override known unit conversions
  - e.g., user should never be able to remap `1 lb = 100g`

- ✅ Density is always stored on the `Ingredient`, not Unit

---

## 🔁 5. Launch Checklist

- [ ] `Unit` table has `is_custom` and `is_mapped` flags
- [ ] `CustomUnitMapping` fully functional with user_id support
- [ ] Density assignment via mapping prompt (optional)
- [ ] Recipe editor blocks unmapped units
- [ ] Stock check blocks:
  - Unmapped units
  - Cross-type units without density
- [ ] Mapping form includes training and validation
- [ ] Messaging clean and non-technical
- [ ] Custom units clearly labeled in UI

---

## 💬 Future Considerations
- Mapping templates: auto-suggest mappings like "pinch", "cup", "scoop"
- Mapping AI assistant: auto-fill suggestions based on patterns
- Shared mapping library (e.g., use what other makers have defined for "scoop")
