# Wall of Drawers Protocol

A cross-cutting UX pattern for resolving user-fixable errors without derailing the current task. Services return a `drawer_payload` that instructs the frontend to open a guided modal or redirect; the browser owns the second request to fetch the drawer, then retries the original action on success.

## Why

- Preserve user flow: fix problems in-context (missing density, unit mapping).
- Encapsulate expertise: each service decides which errors are user-fixable and how to resolve them.
- Decouple layers: backend never calls backend HTTP endpoints; it returns instructions that the browser executes.

## Response Contract

- Services should include a top-level `drawer_payload` in JSON responses when user action is required.
- Drawer interceptor inspects JSON responses and dispatches a global `openDrawer` with the payload.
- The protocol opens the modal via `modal_url` or redirects via `redirect_url`, registers a `success_event`, and triggers retry logic.

Payload fields used in the current implementation:

- `version`: protocol version
- `modal_url`: URL to fetch modal HTML JSON (`{ success, modal_html }`)
- `redirect_url`: alternative to modal
- `success_event`: window event fired by the modal upon completion
- `error_type`, `error_code`, `error_message`: classification
- `correlation_id`: deduplication key
- Optional retry hints: `retry`, `retry_operation`, `retry_data`, or a `retry_callback`

## Frontend Flow

- `app/static/js/core/DrawerInterceptor.js` wraps `window.fetch`, extracts `drawer_payload`, dispatches `openDrawer`.
- `app/static/js/core/DrawerProtocol.js` handles `openDrawer`:
  - stores retry callback or operation
  - redirects or fetches modal HTML from `modal_url`
  - injects HTML, initializes Bootstrap modal
  - listens for `success_event`, executes retry, cleans up

Example modal: `app/templates/components/drawer/density_fix_modal.html`

## Backend Pattern

- Each service owns its `drawer_errors.py` mapping for user-fixable errors.
- Unit Conversion: `app/services/unit_conversion/drawer_errors.py` handles `MISSING_DENSITY`, `MISSING_CUSTOM_MAPPING`, unknown units.
- Container Planning: `app/services/production_planning/drawer_errors.py` handles `MISSING_PRODUCT_DENSITY` (redirect).

Minimal API usage:

```python
result = ConversionEngine.convert_units(...)
if not result['success']:
    drawer_info = handle_conversion_error(result)
    result.update(drawer_info)
return jsonify(result)
```

## Developer Do / Don't

- Do return `drawer_payload` at the top level when user action is needed.
- Do centralize error→drawer mapping in the owning service's `drawer_errors.py`.
- Do emit a specific `success_event` from the modal.
- Don't have backend call drawer endpoints; let the browser make the second request.
- Don't duplicate drawer rules across services; keep domain expertise local.

## Adding a New Drawer

1. Add/extend `<service>/drawer_errors.py` mapping for the error.
2. Implement a drawer actions endpoint returning `{ success, modal_html }`.
3. Build the modal template that dispatches a clear `success_event`.
4. From the API, attach `drawer_payload` when needed.
5. Provide a retry callback or a `retry` block for `DrawerProtocol`.

## Observability

- Log when adding `drawer_payload` for traceability.
- Use `correlation_id` to deduplicate rapid repeats.

## Relation to Global Item Library

Drawers guide users to fix gaps (e.g., density) without corrupting curated `GlobalItem` data. Users set precise per-item values rather than editing library records.