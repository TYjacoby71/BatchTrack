"""Public tools routes.

Synopsis:
Defines public-facing maker tool pages and APIs, including soap calculator
execution and draft handoff into authenticated recipe creation.

Glossary:
- Tool draft: Session-backed payload captured from public tools for later save.
- Soap calculate API: Structured endpoint that delegates full stage computation
  to the soap tool service package.
"""

from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import current_user
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.tools.soap_tool import SoapToolComputationService, get_bulk_catalog_page
from app.services.tools.feedback_note_service import ToolFeedbackNoteService
from app.services.public_bot_trap_service import PublicBotTrapService
from app.models import FeatureFlag
from app.extensions import limiter
from app.utils.cache_utils import should_bypass_cache

# Public Tools blueprint
# Mounted at /tools via blueprints_registry

tools_bp = Blueprint('tools_bp', __name__)

# --- Feature-flag reader ---
# Purpose: Resolve tool enablement from persisted feature flags with fallback.
# Inputs: Feature key and optional default boolean.
# Outputs: Boolean flag value used by route rendering.
def _is_enabled(key: str, default: bool = True) -> bool:
    try:
        flag = FeatureFlag.query.filter_by(key=key).first()
        if flag is not None:
            return bool(flag.enabled)
        return default
    except Exception:
        return default


# --- Tool page renderer ---
# Purpose: Render a tool template with common public-header context.
# Inputs: Template path, feature-flag key, and extra context kwargs.
# Outputs: Flask rendered HTML response.
def _render_tool(template_name: str, flag_key: str, **context):
    enabled = _is_enabled(flag_key, True)
    return render_template(
        template_name,
        tool_enabled=enabled,
        show_public_header=True,
        **context,
    )


# --- Soap quota resolver ---
# Purpose: Determine per-day calc quota based on auth/tier context.
# Inputs: Current user/session organization state.
# Outputs: Tuple of (limit or None, tier label).
def _soap_calc_limit():
    if not getattr(current_user, "is_authenticated", False):
        return 5, "guest"
    org = getattr(current_user, "organization", None)
    tier = getattr(org, "tier", None) if org else None
    tier_name = (tier.name if tier else "") or ""
    if tier_name.lower().startswith("free"):
        return 5, "free"
    return None, tier_name or "paid"


# --- Soap quota consumer ---
# Purpose: Track and enforce rolling 24-hour draft quota for soap category.
# Inputs: Category name from payload and session storage state.
# Outputs: Quota result dict when quota applies, otherwise None.
def _consume_tool_quota(category_name: str | None):
    """Track draft submissions for free/guest tiers (daily rolling window)."""
    normalized = (category_name or "").strip().lower()
    if normalized != "soaps":
        return None
    limit, tier = _soap_calc_limit()
    if not limit:
        return None
    from flask import session
    from datetime import datetime, timezone, timedelta

    key = "soap_tool_quota"
    now = datetime.now(timezone.utc)
    record = session.get(key) or {}
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if now - last_dt > timedelta(hours=24):
                record = {}
    except Exception:
        record = {}

    count = int(record.get("count") or 0)
    if count >= limit:
        return {"ok": False, "limit": limit, "tier": tier, "remaining": 0}

    count += 1
    record["count"] = count
    record["timestamp"] = now.isoformat()
    session[key] = record
    return {"ok": True, "limit": limit, "tier": tier, "remaining": max(0, limit - count)}


# --- Tools landing route ---
# Purpose: Render public tools index with per-tool feature visibility flags.
# Inputs: HTTP request context and feature flag table.
# Outputs: Public tools index HTML response.
@tools_bp.route('/')
@limiter.limit("60000/hour;5000/minute")
def tools_index():
    """Public tools landing. Embeds calculators with progressive disclosure.
    Includes: Unit Converter, Fragrance Load Calculator, Lye Calculator (view-only),
    and quick draft Recipe Tool (category-aware) with Save CTA that invites sign-in.
    """
    flags = {
        'soap': _is_enabled('TOOLS_SOAP', True),
        'candles': _is_enabled('TOOLS_CANDLES', True),
        'lotions': _is_enabled('TOOLS_LOTIONS', True),
        'herbal': _is_enabled('TOOLS_HERBAL', True),
        'baker': _is_enabled('TOOLS_BAKING', True),
    }
    return render_template(
        'tools/index.html',
        tool_flags=flags,
        show_public_header=True,
    )


# --- Soap tool route ---
# Purpose: Render the soap formulator page with quota tier context.
# Inputs: HTTP request/user context.
# Outputs: Soap tool HTML response.
@tools_bp.route('/soap')
def tools_soap():
    calc_limit, calc_tier = _soap_calc_limit()
    return _render_tool('tools/soaps/index.html', 'TOOLS_SOAP', calc_limit=calc_limit, calc_tier=calc_tier)


# --- Candles tool route ---
# Purpose: Render public candles tool page.
# Inputs: HTTP request context.
# Outputs: Candles tool HTML response.
@tools_bp.route('/candles')
def tools_candles():
    return _render_tool('tools/candles.html', 'TOOLS_CANDLES')


# --- Lotions tool route ---
# Purpose: Render public lotions tool page.
# Inputs: HTTP request context.
# Outputs: Lotions tool HTML response.
@tools_bp.route('/lotions')
def tools_lotions():
    return _render_tool('tools/lotions.html', 'TOOLS_LOTIONS')


# --- Herbal tool route ---
# Purpose: Render public herbal tool page.
# Inputs: HTTP request context.
# Outputs: Herbal tool HTML response.
@tools_bp.route('/herbal')
def tools_herbal():
    return _render_tool('tools/herbal.html', 'TOOLS_HERBAL')


# --- Baker tool route ---
# Purpose: Render public baker tool page.
# Inputs: HTTP request context.
# Outputs: Baker tool HTML response.
@tools_bp.route('/baker')
def tools_baker():
    return _render_tool('tools/baker.html', 'TOOLS_BAKING')


# --- Soap calculate API route ---
# Purpose: Execute soap lye/water calculation through service package.
# Inputs: JSON payload with oils/lye/water inputs.
# Outputs: JSON success response with structured calculation result.
@tools_bp.route('/api/soap/calculate', methods=['POST'])
@limiter.limit("60000/hour;5000/minute")
def tools_soap_calculate():
    """Calculate soap stage outputs through structured service package."""
    payload = request.get_json(silent=True) or {}
    result = SoapToolComputationService.calculate(payload)
    return jsonify({"success": True, "result": result})


# --- Soap bulk-oils catalog API route ---
# Purpose: Return paged oils/butters/waxes catalog rows for bulk-oil picker modal.
# Inputs: Query params mode/q/sort/offset/limit for server-side paging/search.
# Outputs: JSON payload with normalized paged records and cursor metadata.
@tools_bp.route('/api/soap/oils-catalog', methods=['GET'])
@limiter.limit("1200/hour;120/minute")
def tools_soap_oils_catalog():
    result_payload = get_bulk_catalog_page(
        mode=request.args.get("mode"),
        query=request.args.get("q"),
        sort_key=request.args.get("sort_key"),
        sort_dir=request.args.get("sort_dir"),
        offset=request.args.get("offset"),
        limit=request.args.get("limit"),
        bypass_cache=should_bypass_cache(),
    )
    return jsonify({"success": True, "result": result_payload})


# --- Public tool feedback notes route ---
# Purpose: Persist public feedback notes into JSON buckets by source/flow.
# Inputs: JSON payload containing source, flow, and note message/details.
# Outputs: JSON response with saved bucket metadata.
@tools_bp.route('/api/feedback-notes', methods=['POST'])
@limiter.limit("1200/hour;120/minute")
def tools_feedback_notes():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    trap_value = (payload.get("website") or payload.get("company") or "").strip()
    trap_email = (payload.get("contact_email") or payload.get("email") or "").strip().lower() or None
    requester_ip = PublicBotTrapService.resolve_request_ip(request)
    requester_user_id = getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None
    note_source = ToolFeedbackNoteService.derive_location_source(
        page_endpoint=payload.get("page_endpoint"),
        page_path=payload.get("page_path"),
        fallback_source=payload.get("source"),
    )

    def _success_passthrough():
        return jsonify({"success": True, "message": "Thanks. Your note was saved."})

    if trap_value:
        PublicBotTrapService.record_hit(
            request=request,
            source=note_source,
            reason="feedback_note_honeypot",
            email=trap_email,
            user_id=requester_user_id,
            extra={"field": "website"},
            block=False,
        )
        if trap_email:
            blocked_user_id = PublicBotTrapService.block_email_if_user_exists(trap_email)
            PublicBotTrapService.add_block(email=trap_email, user_id=blocked_user_id)
        else:
            PublicBotTrapService.add_block(ip=requester_ip, user_id=requester_user_id)
        return _success_passthrough()

    if PublicBotTrapService.is_blocked(
        ip=requester_ip,
        email=trap_email,
        user_id=requester_user_id,
    ):
        PublicBotTrapService.record_hit(
            request=request,
            source=note_source,
            reason="feedback_note_blocked",
            email=trap_email,
            user_id=requester_user_id,
            extra={"page_path": payload.get("page_path")},
            block=False,
        )
        return _success_passthrough()

    request_meta = {
        "ip": requester_ip,
        "user_agent": request.headers.get("User-Agent"),
        "referer": request.headers.get("Referer"),
    }
    source_override = note_source

    try:
        result = ToolFeedbackNoteService.save_note(
            payload,
            request_meta=request_meta,
            user=current_user,
            source_override=source_override,
        )
    except ValueError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "allowed_flows": ToolFeedbackNoteService.allowed_flows(),
                }
            ),
            400,
        )
    except Exception:
        return jsonify({"success": False, "error": "Unable to save your note right now."}), 500

    return jsonify(
        {
            "success": True,
            "message": "Thanks. Your note was saved.",
            "result": result,
        }
    )


# --- Public draft capture route ---
# Purpose: Persist public tool draft payload into session for auth handoff.
# Inputs: JSON draft payload with optional recipe lines.
# Outputs: JSON response with redirect target or quota error.
@tools_bp.route('/draft', methods=['POST'])
def tools_draft():
    """Accept a draft from the public tools page and redirect to sign-in/save flow.
    The draft payload is stored in session via query string for now (MVP), then the
    /recipes/new page will read and prefill when user is authenticated.
    """
    from flask import session
    data = request.get_json() or {}
    quota = _consume_tool_quota(data.get("category_name"))
    if quota and not quota.get("ok"):
        msg = (
            f"Free tools allow {quota['limit']} submissions per day. "
            "Create a free account or upgrade to keep saving drafts."
        )
        return jsonify({"success": False, "error": msg, "limit_reached": True}), 429
    # Normalize line arrays if provided
    def _norm_lines(lines, kind):
        out = []
        for ln in (lines or []):
            try:
                name = (ln.get('name') or '').strip() or None
                gi = ln.get('global_item_id')
                gi = int(gi) if gi not in (None, '', []) else None
                qty = ln.get('quantity')
                try:
                    qty = float(qty) if qty not in (None, '', []) else None
                except Exception:
                    qty = None
                unit = (ln.get('unit') or '').strip() or None
                rec = {
                    'name': name,
                    'global_item_id': gi,
                    'default_unit': (ln.get('default_unit') or '').strip() or None,
                    'ingredient_category_name': (ln.get('ingredient_category_name') or '').strip() or None,
                }
                if kind == 'container':
                    rec['quantity'] = int(qty) if qty is not None else 1
                else:
                    rec['quantity'] = float(qty) if qty is not None else 0.0
                    rec['unit'] = unit or 'gram'
                out.append(rec)
            except Exception:
                continue
        return out

    if 'ingredients' in data:
        data['ingredients'] = _norm_lines(data.get('ingredients'), 'ingredient')
    if 'consumables' in data:
        data['consumables'] = _norm_lines(data.get('consumables'), 'consumable')
    if 'containers' in data:
        data['containers'] = _norm_lines(data.get('containers'), 'container')
    # Merge to preserve any prior progress and keep across redirects
    try:
        from datetime import datetime, timezone
        existing = session.get('tool_draft', {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(data or {})
        session['tool_draft'] = existing

        # Track draft metadata for TTL and debugging
        meta = session.get('tool_draft_meta') or {}
        if not isinstance(meta, dict):
            meta = {}
        if not meta.get('created_at'):
            meta['created_at'] = datetime.now(timezone.utc).isoformat()
        meta['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        meta['source'] = 'public_tools'
        session['tool_draft_meta'] = meta

        # Do NOT make the entire session permanent just for a draft
        # Let session behave normally so drafts end with the browser session
        try:
            session.permanent = False
        except Exception:
            pass
    except Exception:
        session['tool_draft'] = data
        try:
            session.pop('tool_draft_meta', None)
        except Exception:
            pass
    # Redirect to sign-in or directly to recipes new if already logged in
    return jsonify({'success': True, 'redirect': url_for('recipes.new_recipe')})