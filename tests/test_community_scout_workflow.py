import os

from app.extensions import db
from app.models import Organization
from app.models.community_scout import CommunityScoutBatch, CommunityScoutCandidate
from app.models.inventory import InventoryItem
from app.models.unit import Unit
from app.services.community_scout_service import CommunityScoutService


def _login_as_developer(client, developer_user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(developer_user.id)
        sess['_fresh'] = True


def _build_candidate_snapshot(inventory_id: int, organization_id: int) -> dict:
    return {
        'id': inventory_id,
        'organization_id': organization_id,
        'name': 'Leche entera',
        'type': 'ingredient',
        'unit': 'gram',
        'tokens': ['leche', 'entera'],
        'density': 1.03,
        'inci_name': 'Milk',
    }


def test_get_next_batch_leaves_batch_unclaimed(app_context):
    batch = CommunityScoutBatch(status='pending')
    db.session.add(batch)
    db.session.flush()

    candidate = CommunityScoutCandidate(
        batch_id=batch.id,
        organization_id=1,
        inventory_item_id=None,
        item_snapshot_json={'id': 1, 'organization_id': 1, 'name': 'Sample', 'type': 'ingredient', 'unit': 'gram', 'tokens': ['sample']},
        classification='needs_review',
    )
    db.session.add(candidate)
    db.session.commit()

    fetched = CommunityScoutService.get_next_batch()
    assert fetched is not None
    assert fetched.id == batch.id
    assert fetched.status == 'pending'
    assert fetched.claimed_by_user_id is None


def test_full_form_submission_links_candidate(client, developer_user, app_context):
    unit = Unit.query.filter_by(name='gram').first()
    if not unit:
        unit = Unit(name='gram', unit_type='weight', base_unit='gram', conversion_factor=1.0)
        db.session.add(unit)
        db.session.commit()

    org = Organization(name='Scout Org')
    db.session.add(org)
    db.session.flush()

    inventory = InventoryItem(
        name='Leche entera',
        unit='gram',
        type='ingredient',
        organization_id=org.id,
        quantity=1,
    )
    db.session.add(inventory)
    db.session.flush()

    batch = CommunityScoutBatch(status='pending')
    db.session.add(batch)
    db.session.flush()

    candidate = CommunityScoutCandidate(
        batch_id=batch.id,
        organization_id=org.id,
        inventory_item_id=inventory.id,
        item_snapshot_json=_build_candidate_snapshot(inventory.id, org.id),
        classification='needs_review',
    )
    db.session.add(candidate)
    db.session.commit()

    _login_as_developer(client, developer_user)
    response = client.post(
        '/developer/global-items/create',
        data={
            'name': 'Whole Milk Powder',
            'item_type': 'ingredient',
            'default_unit': 'gram',
            'community_scout_candidate_id': str(candidate.id),
            'return_to': '/developer/community-scout',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/developer/community-scout' in response.headers['Location']

    refreshed_candidate = db.session.get(CommunityScoutCandidate, candidate.id)
    assert refreshed_candidate.state == 'resolved'
    assert refreshed_candidate.resolution_payload.get('action') == 'promote'
    global_item_id = refreshed_candidate.resolution_payload.get('global_item_id')
    assert global_item_id is not None

    refreshed_inventory = db.session.get(InventoryItem, inventory.id)
    assert refreshed_inventory.global_item_id == global_item_id


def test_replica_health_missing_config(app_context):
    # Ensure environment variable is unset for this test
    previous = os.environ.pop('COMMUNITY_SCOUT_READ_DSN', None)
    try:
        health = CommunityScoutService.check_replica_health()
        assert health['status'] == 'missing'
    finally:
        if previous is not None:
            os.environ['COMMUNITY_SCOUT_READ_DSN'] = previous
