
# Container Naming Guidelines

## Best Practices for Container Names

### ✅ Recommended Format
Use a concise pattern that encodes capacity first, then name:

`{capacity_value}{capacity_unit} {name}`

Examples:
- `8 fl oz Bottle`
- `16 oz Mason Jar`
- `500 ml Boston Round`
- `4 oz Tin`

This format ensures SKU labels like `{variant} {product} ({container})` render cleanly.

### 🧭 Coaching Rules (free-text but consistent)
- Always include numeric capacity and unit (oz, fl oz, ml, g, lb, L).
- Put capacity at the front; keep the rest short and human-friendly.
- Avoid material/type taxonomies (glass/plastic/amber) unless part of the common name.
- Singular nouns for item name (Bottle, Jar, Tin). Size is handled by capacity.

### ❌ Avoid
- Missing capacity (e.g., `Small Jar`).
- Vague types (`Container A`, `Medium Box`).
- Non-standard units or mixed formats (`8ozs`, `0.5Ltr`).

### 🎯 Why This Matters
- Clean, deterministic SKU size labels and search.
- Reduces duplicates from naming drift.
- Simplifies batch finish flows and reporting.

### 📝 More Examples

Good Names:
- `8 fl oz Bottle`
- `250 ml Amber Bottle`
- `4 oz Tin`
- `32 fl oz Jug`

Poor Names:
- `Big Jar`
- `Container Type A`
- `Medium Box`
- `Regular Bottle`
