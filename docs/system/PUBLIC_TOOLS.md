# Public Tools

## Synopsis
BatchTrack exposes maker-focused public tools under `/tools`, including a full soap formulator and draft handoff into authenticated recipe creation. Public flows are session-backed and integrated with public exports.

## Glossary
- **Tool draft**: Session payload (`tool_draft`) captured from public calculators.
- **Handoff**: Transition from anonymous drafting to authenticated recipe prefill.
- **Public tool API**: Unauthenticated API endpoints mounted under `/tools/api/*`.

## Public Tool Surfaces (Current)

### Index and tool pages
- `/tools`
- `/tools/soap`
- `/tools/candles`
- `/tools/lotions`
- `/tools/herbal`
- `/tools/baker`

### Soap APIs
- `/tools/api/soap/calculate`
- `/tools/api/soap/recipe-payload`
- `/tools/api/soap/quality-nudge`
- `/tools/api/soap/oils-catalog`

### Feedback API
- `/tools/api/feedback-notes`

## Draft Capture and Handoff
- Client posts draft payload to `/tools/draft`.
- Server normalizes line arrays and merges into `session['tool_draft']`.
- Metadata is tracked in `session['tool_draft_meta']`.
- Response includes redirect target for recipe creation flow (`/recipes/new`).

## Quotas and Access
- Soap draft submissions are quota-limited for guest/free contexts in a rolling 24-hour window.
- Public routes are allow-listed via route access policy.

## Search/Typeahead Inputs
- Public typeahead uses `/api/public/global-items/search`.
- Authenticated inventory forms may use `/api/ingredients/global-items/search`.

## Export Integration
Tool drafts can be exported through `/exports/tool/*` routes:
- HTML preview
- CSV
- PDF

## Relevance Check (2026-02-17)
Validated against:
- `app/routes/tools_routes.py`
- `app/blueprints/api/public.py`
- `app/routes/exports_routes.py`
- `app/route_access.py`
