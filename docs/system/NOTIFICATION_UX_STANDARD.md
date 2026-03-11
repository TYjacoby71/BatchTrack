# Notification UX Standard

## Synopsis
This standard defines which notification type to use in BatchTrack, when to use it, and how to implement notifications consistently across backend routes, frontend modules, and drawer workflows.

## Goals
- Remove inconsistent browser-native dialogs (`alert`, `confirm`) from primary flows.
- Keep messaging predictable across pages and features.
- Ensure severity, timing, and user actions are handled consistently.

## Notification Types

### 1) Inline alert (default)
Use for most success, warning, and error messages that do not require a decision.

- UI: Bootstrap alert in page context.
- Behavior: dismissible and optionally auto-hide.
- Typical source:
  - Server redirect/postback: Flask `flash(...)` rendered in `content_chrome.html`.
  - Client async actions: shared JS notification helper.

### 2) Toast (ephemeral feedback)
Use for short-lived, non-critical confirmations.

- UI: bootstrap toast.
- Behavior: auto-hide quickly; no blocking.
- Examples:
  - "Copied to clipboard"
  - "Autosaved"

### 3) Modal (blocking decision)
Use when user must confirm, choose, or acknowledge a high-impact action.

- UI: bootstrap modal.
- Behavior: blocks flow until explicit choice.
- Examples:
  - Destructive confirms (cancel batch, archive/expire inventory)
  - Force-start with shortages
  - Multi-step decisions

### 4) Drawer modal (guided recovery)
Use for recoverable, domain-specific errors requiring in-context fixes.

- Contract: `drawer_payload` + `DrawerInterceptor` + `DrawerProtocol`.
- See `WALL_OF_DRAWERS_PROTOCOL.md`.

### 5) Native browser dialog (`alert`, `confirm`) (restricted)
Do not use in standard feature paths.

- Allowed only as emergency fallback when UI framework is unavailable.
- Must include TODO for migration.

## Decision Matrix
- Need a user decision before continuing? -> **Modal**.
- Informational/success/error with no decision? -> **Inline alert**.
- Very short "completed" feedback? -> **Toast**.
- Recoverable domain error with guided fix? -> **Drawer modal**.
- Never choose native dialogs unless hard fallback is required.

## Implementation Process for New Work
1. Classify message intent (info/success/warn/error/decision/recovery).
2. Choose type from Decision Matrix.
3. Use existing shared pathway:
   - Server -> `flash(...)` + global flash renderer.
   - Client -> shared notification helper.
   - Recovery flow -> drawer protocol.
4. Set severity copy:
   - `success`: completion and next state.
   - `warning`: user can continue with caution.
   - `error`: failed action + clear next step.
5. Avoid adding module-specific one-off helpers unless justified.
6. If a module needs custom behavior, document rationale in the module and in system docs.

## Migration Priorities
- **P1:** Replace native `alert()` and `confirm()` in production-planning, batch, drawer fallback, and destructive inventory flows.
- **P2:** Consolidate duplicated module-local helpers into one shared client helper.
- **P3:** Keep server flash sources; standardize copy and categories over time.

## Review Checklist (for PRs)
- No new native `alert()` or `confirm()` calls added.
- Correct type chosen (inline alert/toast/modal/drawer).
- Error messages include actionable next step.
- If backend uses `flash`, category is explicit and mapped to Bootstrap class.
- Documentation updated when adding a new notification pattern.

## Reference Implementation Points
- Global flash renderer: `app/templates/components/layout/content_chrome.html`
- Global helper baseline: `app/static/js/main.js` (`showAlert`)
- Drawer protocol: `app/static/js/core/DrawerProtocol.js`
- Drawer UX spec: `docs/system/WALL_OF_DRAWERS_PROTOCOL.md`
