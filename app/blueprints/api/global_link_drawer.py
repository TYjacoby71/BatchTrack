from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from ...models import db, InventoryItem, GlobalItem, UnifiedInventoryHistory
from ...services.drawers.payloads import build_drawer_payload
from ...services.global_link_suggestions import GlobalLinkSuggestionService
from ...utils.permissions import require_permission


global_link_bp = Blueprint('global_link', __name__, url_prefix='/global-link')


@global_link_bp.route('/api/check')
@login_required
@require_permission('inventory.view')
def check_needed():
    """Return whether there are suggested links for the current org and a modal URL if so."""
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return jsonify({'needs_drawer': False})

    gi, items = GlobalLinkSuggestionService.get_first_suggestion_for_org(org_id)
    needs = bool(gi and items)
    payload = None
    if needs:
        payload = build_drawer_payload(
            modal_url=f"/global-link/api/modal?global_item_id={gi.id}",
            error_type='global_link',
            error_code='SUGGESTIONS_FOUND',
            success_event='globalLinking.completed'
        )
    return jsonify({'needs_drawer': needs, 'drawer_payload': payload})


@global_link_bp.route('/api/modal')
@login_required
@require_permission('inventory.view')
def get_modal():
    gi_id = request.args.get('global_item_id', type=int)
    org_id = getattr(current_user, 'organization_id', None)
    gi = db.session.get(GlobalItem, gi_id) if gi_id else None
    if not gi or not org_id:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    items = GlobalLinkSuggestionService.find_candidates_for_global(gi.id, org_id)
    html = render_template('components/drawer/global_link_modal.html', global_item=gi, items=items)
    return jsonify({'success': True, 'modal_html': html})


@global_link_bp.route('/api/confirm', methods=['POST'])
@login_required
@require_permission('inventory.edit')
def confirm_link():
    data = request.get_json(force=True) or {}
    gi_id = data.get('global_item_id')
    ids = data.get('item_ids') or []
    gi = db.session.get(GlobalItem, int(gi_id)) if gi_id else None
    if not gi:
        return jsonify({'success': False, 'error': 'Global item not found'}), 404

    updated = 0
    skipped = 0
    for raw_id in ids:
        try:
            inv = db.session.get(InventoryItem, int(raw_id))
            if not inv:
                skipped += 1
                continue
            # Scope to org
            if getattr(current_user, 'organization_id', None) and inv.organization_id != current_user.organization_id:
                skipped += 1
                continue
            # Idempotent: skip already linked
            if getattr(inv, 'global_item_id', None):
                skipped += 1
                continue
            # Ensure pair compatibility with global default unit
            if not gi.default_unit:
                skipped += 1
                continue
            from ...services.global_link_suggestions import GlobalLinkSuggestionService
            if not GlobalLinkSuggestionService.is_pair_compatible(gi.default_unit, inv.unit):
                skipped += 1
                continue

            # Apply linking rules: rename, set density, link; do not change unit
            old_name = inv.name
            inv.name = gi.name
            if gi.density is not None:
                inv.density = gi.density
            inv.global_item_id = gi.id
            if inv.type == 'ingredient':
                inv.saponification_value = gi.saponification_value
                inv.iodine_value = gi.iodine_value
                inv.melting_point_c = gi.melting_point_c
                inv.flash_point_c = gi.flash_point_c
                inv.ph_value = gi.ph_value
                inv.moisture_content_percent = gi.moisture_content_percent
                inv.comedogenic_rating = gi.comedogenic_rating
                inv.recommended_usage_rate = gi.recommended_usage_rate
                inv.recommended_fragrance_load_pct = gi.recommended_fragrance_load_pct
                inv.inci_name = gi.inci_name
                inv.protein_content_pct = gi.protein_content_pct
                inv.brewing_color_srm = gi.brewing_color_srm
                inv.brewing_potential_sg = gi.brewing_potential_sg
                inv.brewing_diastatic_power_lintner = gi.brewing_diastatic_power_lintner
                inv.fatty_acid_profile = gi.fatty_acid_profile
                inv.certifications = gi.certifications
            # ownership auto-derives in model listeners

            # Persist an audit note via UnifiedInventoryHistory with zero quantity change
            evt = UnifiedInventoryHistory(
                inventory_item_id=inv.id,
                change_type='link_global',
                quantity_change=0.0,
                unit=inv.unit or 'count',
                notes=f"Linked to GlobalItem '{gi.name}' (was '{old_name}')",
                created_by=getattr(current_user, 'id', None),
                organization_id=inv.organization_id
            )
            db.session.add(evt)
            updated += 1
        except Exception:
            skipped += 1
            continue

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'updated': updated, 'skipped': skipped})

