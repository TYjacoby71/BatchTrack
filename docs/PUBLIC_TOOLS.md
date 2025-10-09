# Public Tools

Public calculators and draft flow available at `/tools`.

## Draft flow
- Users (anon allowed) fill category fields and select lines.
- Client posts to `/tools/draft` with:
  - ingredients: [{ name, global_item_id?, quantity, unit }]
  - consumables: [{ name, global_item_id?, quantity, unit }]
  - containers: [{ name?, global_item_id?, quantity }]
  - name, instructions, predicted_yield, predicted_yield_unit, category_name, optional category_data
- Server merges into `session['tool_draft']` and persists session.
- `/recipes/new` reads `session['tool_draft']` to prefill form once user signs in.

## Typeahead
- Uses public endpoint: `GET /api/public/global-items/search?type=ingredient|container|consumable`.
- No org endpoints are called unauthenticated.

## Exports
- Public HTML preview: `/exports/tool/...`
- CSV/PDF: `/exports/tool/...(.csv|.pdf)`
