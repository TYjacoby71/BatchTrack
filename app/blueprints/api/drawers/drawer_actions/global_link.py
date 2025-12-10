from flask import jsonify, render_template, request, url_for
from flask_login import login_required, current_user

from app.models import GlobalItem, InventoryItem, UnifiedInventoryHistory, db
from app.services.drawers.payloads import build_drawer_payload
from app.services.global_link_suggestions import GlobalLinkSuggestionService
from app.utils.permissions import require_permission

from .. import drawers_bp, register_cadence_check, register_drawer_action


register_drawer_action(
    'global_link.modal',
    description='Link local inventory items to curated Global Items.',
    endpoint='drawers.global_link_modal',
    success_event='globalLinking.completed',
)


def _build_global_link_payload(global_item_id: int | None):
    if not global_item_id:
        return None
    return build_drawer_payload(
        modal_url=url_for('drawers.global_link_modal', global_item_id=global_item_id),
        error_type='global_link',
        error_code='SUGGESTIONS_FOUND',
        success_event='globalLinking.completed',
    )


def _global_link_drawer_payload():
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return None

    global_item, items = GlobalLinkSuggestionService.get_first_suggestion_for_org(org_id)
    if not (global_item and items):
        return None

    payload = _build_global_link_payload(global_item.id)
    payload['metadata'] = {'suggested_count': len(items)}
    return payload


@register_cadence_check('global_link')
def global_link_cadence_check():
    if not current_user.is_authenticated:
        return None
    return _global_link_drawer_payload()


@drawers_bp.route('/global-link/check', methods=['GET'])
@login_required
@require_permission('inventory.view')
def global_link_check():
    """Check whether the org has suggested global link matches."""
    payload = _global_link_drawer_payload()
    return jsonify({'needs_drawer': payload is not None, 'drawer_payload': payload})


@drawers_bp.route('/global-link/modal', methods=['GET'])
@login_required
@require_permission('inventory.view')
def global_link_modal():
    global_item_id = request.args.get('global_item_id', type=int)
    org_id = getattr(current_user, 'organization_id', None)
    global_item = db.session.get(GlobalItem, global_item_id) if global_item_id else None

    if not global_item or not org_id:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    items = GlobalLinkSuggestionService.find_candidates_for_global(global_item.id, org_id)
    html = render_template('components/drawer/global_link_modal.html', global_item=global_item, items=items)
    return jsonify({'success': True, 'modal_html': html})


@drawers_bp.route('/global-link/confirm', methods=['POST'])
@login_required
@require_permission('inventory.edit')
def global_link_confirm():
    data = request.get_json(force=True) or {}
    global_item_id = data.get('global_item_id')
    item_ids = data.get('item_ids') or []

    global_item = db.session.get(GlobalItem, int(global_item_id)) if global_item_id else None
    if not global_item:
        return jsonify({'success': False, 'error': 'Global item not found'}), 404

    updated = 0
    skipped = 0

    for raw_id in item_ids:
        try:
            inventory_item = db.session.get(InventoryItem, int(raw_id))
            if not inventory_item:
                skipped += 1
                continue

            if getattr(current_user, 'organization_id', None) and inventory_item.organization_id != current_user.organization_id:
                skipped += 1
                continue

            if getattr(inventory_item, 'global_item_id', None):
                skipped += 1
                continue

            if not global_item.default_unit:
                skipped += 1
                continue

            if not GlobalLinkSuggestionService.is_pair_compatible(global_item.default_unit, inventory_item.unit):
                skipped += 1
                continue

            old_name = inventory_item.name
            inventory_item.name = global_item.name
            if global_item.density is not None:
                inventory_item.density = global_item.density
            inventory_item.global_item_id = global_item.id

            if inventory_item.type == 'ingredient':
                inventory_item.saponification_value = global_item.saponification_value
                inventory_item.iodine_value = global_item.iodine_value
                inventory_item.melting_point_c = global_item.melting_point_c
                inventory_item.flash_point_c = global_item.flash_point_c
                inventory_item.ph_value = global_item.ph_value
                inventory_item.moisture_content_percent = global_item.moisture_content_percent
                inventory_item.comedogenic_rating = global_item.comedogenic_rating
                
                inventory_item.recommended_fragrance_load_pct = global_item.recommended_fragrance_load_pct
                inventory_item.inci_name = global_item.inci_name
                inventory_item.protein_content_pct = global_item.protein_content_pct
                inventory_item.brewing_color_srm = global_item.brewing_color_srm
                inventory_item.brewing_potential_sg = global_item.brewing_potential_sg
                inventory_item.brewing_diastatic_power_lintner = global_item.brewing_diastatic_power_lintner
                inventory_item.fatty_acid_profile = global_item.fatty_acid_profile
                inventory_item.certifications = global_item.certifications

            history_event = UnifiedInventoryHistory(
                inventory_item_id=inventory_item.id,
                change_type='link_global',
                quantity_change=0.0,
                unit=inventory_item.unit or 'count',
                notes=f"Linked to GlobalItem '{global_item.name}' (was '{old_name}')",
                created_by=getattr(current_user, 'id', None),
                organization_id=inventory_item.organization_id,
            )
            db.session.add(history_event)
            updated += 1
        except Exception:
            skipped += 1
            continue

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 500

    return jsonify({'success': True, 'updated': updated, 'skipped': skipped})
