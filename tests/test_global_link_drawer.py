import json
import pytest


@pytest.mark.usefixtures("app", "db_session")
def test_global_link_suggestions_and_link_flow(app, db_session):
    from app.models import InventoryItem, GlobalItem, IngredientCategory, Unit, User, Organization

    # Ensure base units exist (weight, volume, count)
    if not Unit.query.filter_by(name='g').first():
        db_session.add(Unit(name='g', symbol='g', unit_type='weight', conversion_factor=1.0))
    if not Unit.query.filter_by(name='ml').first():
        db_session.add(Unit(name='ml', symbol='ml', unit_type='volume', conversion_factor=1.0))
    if not Unit.query.filter_by(name='count').first():
        db_session.add(Unit(name='count', symbol='ct', unit_type='count', conversion_factor=1.0))
    db_session.commit()

    # Create org and user context
    org = Organization(name='Test Org')
    db_session.add(org)
    db_session.flush()

    user = User(email='test@example.com', user_type='developer', is_active=True, organization_id=org.id)
    db_session.add(user)
    db_session.commit()

    # Create a curated category and global item 'Milk' stored in volume (ml) with density
    cat = IngredientCategory(name='Liquids', default_density=1.0, organization_id=None, is_global_category=True)
    db_session.add(cat)
    db_session.flush()

    gi = GlobalItem(name='Milk', item_type='ingredient', default_unit='ml', density=1.03, ingredient_category_id=cat.id)
    db_session.add(gi)
    db_session.commit()

    # Create org inventory items: matchable and non-matchable
    milk_ml = InventoryItem(name='milk', type='ingredient', unit='ml', quantity=0.0, organization_id=org.id)
    milk_g = InventoryItem(name='MILK', type='ingredient', unit='g', quantity=0.0, organization_id=org.id)
    milk_count = InventoryItem(name='milk (units)', type='ingredient', unit='count', quantity=0.0, organization_id=org.id)
    db_session.add_all([milk_ml, milk_g, milk_count])
    db_session.commit()

    # Create flask client with the provided app fixture to share the same DB
    app.config['SKIP_PERMISSIONS'] = True
    with app.test_client() as client:
        # Login helper: set session org and auth
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
            # Developer scoping to org
            sess['dev_selected_org_id'] = org.id
        # Check suggestions
        res = client.get('/api/drawers/global-link/check')
        assert res.status_code == 200
        data = res.get_json() or {}
        assert 'needs_drawer' in data
        # Depending on which global has candidates, the service returns first; ensure payload present when true
        if data['needs_drawer']:
            assert data.get('drawer_payload', {}).get('modal_url')

        # Force modal for our specific global item
        res2 = client.get(f'/api/drawers/global-link/modal?global_item_id={gi.id}')
        assert res2.status_code == 200
        html_payload = res2.get_json() or {}
        assert html_payload.get('success') is True
        assert 'modal_html' in html_payload
        # The modal should list ml and g items but not count
        html = html_payload['modal_html']
        assert 'MILK' in html or 'Milk' in html  # will become name
        assert f'value="{milk_ml.id}"' in html
        assert f'value="{milk_g.id}"' in html
        assert f'value="{milk_count.id}"' not in html  # non-convertible count excluded

        # Confirm linking for ml and g
        payload = {
            'global_item_id': gi.id,
            'item_ids': [milk_ml.id]
        }
        res3 = client.post('/api/drawers/global-link/confirm', data=json.dumps(payload), content_type='application/json')
        assert res3.status_code == 200
        result = res3.get_json()
        assert result.get('success') is True
        assert result.get('updated') == 1

        # Reload items and verify link applied, unit unchanged, density set
        db_session.refresh(milk_ml)
        db_session.refresh(milk_g)
        assert milk_ml.global_item_id == gi.id
        assert milk_g.global_item_id is None
        assert milk_ml.unit == 'ml'  # unchanged
        assert milk_g.unit == 'g'    # unchanged
        assert abs(milk_ml.density - 1.03) < 1e-6
        assert milk_g.density in (None, 0.0)

        # Ensure non-convertible was not linked
        db_session.refresh(milk_count)
        assert milk_count.global_item_id is None

