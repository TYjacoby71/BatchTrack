from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import current_user
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.tools.soap_calculator import SoapToolCalculatorService
from app.models import GlobalItem
from app.models import FeatureFlag
from app.extensions import limiter

# Public Tools blueprint
# Mounted at /tools via blueprints_registry

tools_bp = Blueprint('tools_bp', __name__)

def _is_enabled(key: str, default: bool = True) -> bool:
    try:
        flag = FeatureFlag.query.filter_by(key=key).first()
        if flag is not None:
            return bool(flag.enabled)
        return default
    except Exception:
        return default


def _render_tool(template_name: str, flag_key: str, **context):
    enabled = _is_enabled(flag_key, True)
    return render_template(
        template_name,
        tool_enabled=enabled,
        show_public_header=True,
        **context,
    )


def _soap_calc_limit():
    if not getattr(current_user, "is_authenticated", False):
        return 5, "guest"
    org = getattr(current_user, "organization", None)
    tier = getattr(org, "tier", None) if org else None
    tier_name = (tier.name if tier else "") or ""
    if tier_name.lower().startswith("free"):
        return 5, "free"
    return None, tier_name or "paid"


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

@tools_bp.route('/soap')
def tools_soap():
    calc_limit, calc_tier = _soap_calc_limit()
    return _render_tool('tools/soaps/index.html', 'TOOLS_SOAP', calc_limit=calc_limit, calc_tier=calc_tier)

@tools_bp.route('/candles')
def tools_candles():
    return _render_tool('tools/candles.html', 'TOOLS_CANDLES')

@tools_bp.route('/lotions')
def tools_lotions():
    return _render_tool('tools/lotions.html', 'TOOLS_LOTIONS')

@tools_bp.route('/herbal')
def tools_herbal():
    return _render_tool('tools/herbal.html', 'TOOLS_HERBAL')

@tools_bp.route('/baker')
def tools_baker():
    return _render_tool('tools/baker.html', 'TOOLS_BAKING')


@tools_bp.route('/api/soap/calculate', methods=['POST'])
@limiter.limit("60000/hour;5000/minute")
def tools_soap_calculate():
    """Calculate soap lye/water values through structured service package."""
    payload = request.get_json(silent=True) or {}
    result = SoapToolCalculatorService.calculate(payload)
    return jsonify({"success": True, "result": result.to_dict()})


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