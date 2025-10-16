from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.models import GlobalItem
from app.models import FeatureFlag

# Public Tools blueprint
# Mounted at /tools via blueprints_registry

tools_bp = Blueprint('tools_bp', __name__)

def _is_enabled(key: str, default: bool = True) -> bool:
    try:
        flag = FeatureFlag.query.filter_by(key=key).first()
        if flag is None:
            return default
        return bool(flag.enabled)
    except Exception:
        return default


@tools_bp.route('/')
def tools_index():
    """Public tools landing. Embeds calculators with progressive disclosure.
    Includes: Unit Converter, Fragrance Load Calculator, Lye Calculator (view-only),
    and quick draft Recipe Tool (category-aware) with Save CTA that invites sign-in.
    """
    flags = {
        'soap': _is_enabled('tools.soap', True),
        'candles': _is_enabled('tools.candles', True),
        'lotions': _is_enabled('tools.lotions', True),
        'herbal': _is_enabled('tools.herbal', True),
        'baker': _is_enabled('tools.baker', True),
    }
    return render_template('tools/index.html', tool_flags=flags)

@tools_bp.route('/soap')
def tools_soap():
    if not _is_enabled('tools.soap', True):
        flash('Soap tools are currently unavailable.', 'warning')
        return redirect(url_for('tools_bp.tools_index'))
    return render_template('tools/soap.html')

@tools_bp.route('/candles')
def tools_candles():
    if not _is_enabled('tools.candles', True):
        flash('Candle tools are currently unavailable.', 'warning')
        return redirect(url_for('tools_bp.tools_index'))
    return render_template('tools/candles.html')

@tools_bp.route('/lotions')
def tools_lotions():
    if not _is_enabled('tools.lotions', True):
        flash('Lotion tools are currently unavailable.', 'warning')
        return redirect(url_for('tools_bp.tools_index'))
    return render_template('tools/lotions.html')

@tools_bp.route('/herbal')
def tools_herbal():
    if not _is_enabled('tools.herbal', True):
        flash('Herbal tools are currently unavailable.', 'warning')
        return redirect(url_for('tools_bp.tools_index'))
    return render_template('tools/herbal.html')

@tools_bp.route('/baker')
def tools_baker():
    if not _is_enabled('tools.baker', True):
        flash('Baker tools are currently unavailable.', 'warning')
        return redirect(url_for('tools_bp.tools_index'))
    return render_template('tools/baker.html')


@tools_bp.route('/draft', methods=['POST'])
def tools_draft():
    """Accept a draft from the public tools page and redirect to sign-in/save flow.
    The draft payload is stored in session via query string for now (MVP), then the
    /recipes/new page will read and prefill when user is authenticated.
    """
    from flask import session
    data = request.get_json() or {}
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
                rec = {'name': name, 'global_item_id': gi}
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
        existing = session.get('tool_draft', {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(data or {})
        session['tool_draft'] = existing
        session.permanent = True
    except Exception:
        session['tool_draft'] = data
        session.permanent = True
    # Redirect to sign-in or directly to recipes new if already logged in
    return jsonify({'success': True, 'redirect': url_for('recipes.new_recipe')})
