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

### Standard Payload Builder (Recommended)

- Backends should construct payloads via a small helper to ensure shape consistency and future schema evolution without churn. Fields:
  - `modal_url` (required)
  - `error_type` (required, namespace e.g., `global_link`)
  - `error_code` (required, case label e.g., `SUGGESTIONS_FOUND`)
  - `success_event` (optional, convention: `<feature>.completed`)
  - `correlation_id` (optional; backend-provided when server-side cadence/dedupe is available)
  - No arbitrary fields unless strictly needed.

Example builder:

```python
def build_drawer_payload(modal_url: str, *, error_type: str, error_code: str, success_event: str | None = None, correlation_id: str | None = None):
    payload = {
        'modal_url': modal_url,
        'error_type': error_type,
        'error_code': error_code,
    }
    if success_event:
        payload['success_event'] = success_event
    if correlation_id:
        payload['correlation_id'] = correlation_id
    return payload
```

## Frontend Flow

- `app/static/js/core/DrawerInterceptor.js` wraps `window.fetch`, extracts `drawer_payload`, dispatches `openDrawer`.
- `app/static/js/core/DrawerProtocol.js` listens for `openDrawer` and:
  - stores retry callbacks/operations keyed by event + correlation id
  - redirects or fetches modal HTML
  - injects the HTML into a `.drawer-wrapper`, executing inline scripts
  - listens for `success_event`, runs the retry, cleans up the modal
  - emits `drawer.analytics` events for observability
- `app/static/js/drawers/drawer_cadence.js` proactively calls `/api/drawers/check` to surface cadence-based drawers (retention, global link, etc.) without bespoke pollers.
- Drawer-specific helpers live under `app/static/js/drawers/` when a modal needs extra behavior (e.g., `container_unit_mismatch_drawer.js`).

Example modal template: `app/templates/components/drawer/container_unit_mismatch_drawer.html`

### Common success events

- `conversion.density.updated` — density saved for an ingredient
- `conversion.unit_mapping.created` — new custom unit mapping created
- `globalLinking.completed` — inventory items linked to a GlobalItem
- `inventory.quick_create.completed` — quick-create inventory finished
- `container.plan.updated` — container planning fix completed

Use a specific, namespaced event per drawer so `DrawerProtocol` can bind and retry reliably.

### File Locations & Conventions

- **Frontend core**
  - Interceptor: `app/static/js/core/DrawerInterceptor.js`
  - Protocol: `app/static/js/core/DrawerProtocol.js`
  - Cadence poller: `app/static/js/drawers/drawer_cadence.js`
  - Drawer-specific helpers: `app/static/js/drawers/*.js`
- **Backend**
  - Drawer API + registry: `app/blueprints/api/drawers/__init__.py`
  - Per-drawer action modules: `app/blueprints/api/drawers/drawer_actions/*.py`
  - Payload builder: `app/services/drawers/payloads.py`
  - Service-level drawer logic: `<service>/drawer_errors.py`
- **Templates**
  - Modal HTML: `app/templates/components/drawer/*.html`

All core scripts are loaded globally via `app/templates/layout.html` so drawers work everywhere.

## Backend Pattern

- Each service owns its `drawer_errors.py` mapping for user-fixable errors.
- Unit Conversion: `app/services/unit_conversion/drawer_errors.py` handles `MISSING_DENSITY`, `MISSING_CUSTOM_MAPPING`, unknown units.
- Container Planning: `app/services/production_planning/drawer_errors.py` handles `MISSING_PRODUCT_DENSITY` (redirect).

### Drawer API Blueprint & Registry

`app/blueprints/api/drawers/__init__.py` owns:

- `DrawerRegistry`: keeps a catalog of drawer actions + cadence checks.
- `/api/drawers/check`: runs registered cadence checks (`?include=x` to scope) and returns pending payloads.
- Imports `drawer_actions/*` for side-effect registration. Each module:
  - Registers its action metadata with `register_drawer_action`
  - Defines the modal/submit routes under `/api/drawers/...`
  - Optionally registers cadence checks via `register_cadence_check`

Cadence examples:

- Retention drawers: `/api/drawers/retention/*`
- Global link drawers: `/api/drawers/global-link/*`
- Containers, conversion, quick-create, etc. live under `drawer_actions/`.

## Developer Do / Don't

- Do return `drawer_payload` at the top level when user action is needed.
- Do centralize error→drawer mapping in the owning service's `drawer_errors.py`.
- Do emit a specific `success_event` from the modal.
- Do follow naming conventions: `error_type.feature`, `error_code.case`, `success_event` as `<feature>.completed`.
- Do ensure accessibility: label via `aria-labelledby`, keyboard focus management, and descriptive button text.
- Don't have backend call drawer endpoints; let the browser make the second request.
- Don't duplicate drawer rules across services; keep domain expertise local.

## Adding a New Drawer (Detailed Checklist)

1. **Decide ownership**
   - Pick/extend the owning service’s `drawer_errors.py`.
   - Choose `error_type`, `error_code`, `success_event`, and retry semantics.

2. **Create/extend payload mapping**
   - Build payloads via `build_drawer_payload(...)`.
   - Include `success_event`, `correlation_id`, and `retry` hints (either `retry` or legacy `retry_operation` + `retry_data`).

3. **Return payloads from service/controller**
   - On user-fixable errors, attach `drawer_payload` at the top level (or inside `data.drawer_payload` for nested APIs).
   - Log when payloads are emitted for traceability.

4. **Register drawer action**
   - Add a new module under `app/blueprints/api/drawers/drawer_actions/`.
   - Call `register_drawer_action('feature.case', endpoint='drawers.my_action', success_event='feature.completed', description='…')`.
   - Define the modal GET route (returns `{success, modal_html}`).
   - Define any POST routes hit by the modal.
   - Secure with `@login_required` + `@require_permission(...)`.

5. **Create modal template**
   - Add `app/templates/components/drawer/<name>.html`.
   - Use Bootstrap modal markup, include CSRF tokens, success/error banners, etc.
   - Emit the agreed `success_event` (via inline script or dedicated JS file).

6. **Add optional JS helper**
   - For drawers needing client logic beyond basic form posts, add `app/static/js/drawers/<name>.js`.
   - Load it globally via `layout.html` if the drawer can appear anywhere.

7. **Hook into cadence (optional)**
   - If the drawer should be polled periodically, register a cadence check with `register_cadence_check('id')` in the drawer action module.
   - Ensure the cadence handler returns either `None` or a full payload (and ideally sets `payload['source']`).

8. **Testing**
   - Add/extend pytest coverage to hit `/api/drawers/...` endpoints.
   - Exercise service flows to confirm payloads and retries.
   - Validate frontend behavior (DrawerInterceptor + DrawerProtocol auto-open the drawer).

Following this checklist keeps drawer UX consistent and discoverable across services.

### Minimal End-to-End Example

- Build payload (service/controller):

```python
from app.services.drawers.payloads import build_drawer_payload

payload = build_drawer_payload(
    modal_url=f"/api/drawers/conversion/density-modal/{ingredient.id}",
    error_type='conversion',
    error_code='MISSING_DENSITY',
    success_event='densityUpdated'
)

response = { 'success': False, 'error': 'Missing density', 'drawer_payload': payload }
return jsonify(response)
```

- Drawer actions route returns modal HTML:

```python
@drawers_bp.route('/conversion/density-modal/<int:ingredient_id>')
def density_modal(ingredient_id):
    modal_html = render_template('components/drawer/density_fix_modal.html', ingredient=ingredient)
    return jsonify({'success': True, 'modal_html': modal_html})
```

- Modal template emits success event on completion:

```html
<div class="modal" id="densityFixModal" aria-labelledby="densityFixModalLabel" role="dialog">
  <!-- form fields -->
  <button id="saveDensity" class="btn btn-primary">Save</button>
</div>
<script>
document.getElementById('saveDensity').addEventListener('click', async () => {
  // submit density change via existing endpoint
  // on success, emit the agreed event name so DrawerProtocol retries the original op
  window.dispatchEvent(new CustomEvent('densityUpdated', { detail: { ingredientId: {{ ingredient.id }} } }));
});
</script>
```

### Required Listeners & Retries

- Global listeners are already provided by `DrawerInterceptor.js` and `DrawerProtocol.js`.
- Always provide a `success_event` in the payload and dispatch it from the modal when the fix is complete.
- Provide retry metadata: either
  - `retry`: `{ operation: 'stock_check', data: { recipe_id } }`, or
  - legacy `retry_operation`/`retry_data` fields.
- `DrawerProtocol` will automatically execute the provided retry after the success event.

## Cadence, Dedupe, and Telemetry

- Cadence: Prefer server-driven weekly cadence per org/user. Client-side localStorage gating is acceptable as a starter.
- Dedupe: Provide `correlation_id` when possible to avoid duplicate opens.
- Analytics: Emit `open`, `continue`, `dismiss` events for each drawer with `error_type`, `error_code`, and `correlation_id` for measurement.

## Observability

- Log when adding `drawer_payload` for traceability.
- Use `correlation_id` to deduplicate rapid repeats.

## Relation to Global Item Library

Drawers guide users to fix gaps (e.g., density) without corrupting curated `GlobalItem` data. Users set precise per-item values rather than editing library records.