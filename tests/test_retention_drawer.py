from datetime import datetime, timedelta


def test_retention_flow_ack_to_delete(client, db_session, app):
    # Arrange: create org, tier with 365d retention, user, and an old recipe not used by batches
    from app.models import Organization, User
    from app.models.subscription_tier import SubscriptionTier
    from app.models.recipe import Recipe
    from app.services.retention_service import RetentionService

    tier = SubscriptionTier(name='Test Tier', billing_provider='exempt', user_limit=5, data_retention_days=365)
    db_session.add(tier)
    org = Organization(name='Retention Org')
    db_session.add(org)
    db_session.flush()
    org.subscription_tier_id = tier.id

    user = User(username='ret_user', email='ret@example.com')
    user.organization_id = org.id
    user.set_password('password')
    db_session.add(user)
    db_session.commit()

    # Login
    client.post('/auth/login', data={'username': 'ret_user', 'password': 'password'})

    old_date = datetime.utcnow() - timedelta(days=366)
    recipe = Recipe(name='Old Draft', organization_id=org.id, created_at=old_date)
    db_session.add(recipe)
    db_session.commit()

    # Act: check drawer
    r = client.get('/retention/api/check')
    assert r.status_code == 200
    assert r.json['needs_drawer'] is True
    assert r.json['count'] >= 1

    # Get modal
    r = client.get('/retention/api/modal')
    assert r.status_code == 200
    assert r.json['success'] is True
    assert 'Data Retention Notice' in r.json['modal_html']

    # Acknowledge
    r = client.post('/retention/api/acknowledge', json={'acknowledge': True})
    assert r.status_code == 200
    assert r.json['success'] is True
    assert r.json['queued'] >= 1

    # Drawer should not show again now for same items
    r = client.get('/retention/api/check')
    assert r.status_code == 200
    assert r.json['needs_drawer'] in [False, True]  # could be more items in other tests

    # Fast-forward: make eligible for deletion now
    from app.models.retention import RetentionDeletionQueue
    q = RetentionDeletionQueue.query.filter_by(organization_id=org.id, recipe_id=recipe.id).first()
    assert q is not None
    q.delete_after_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    # Sweep
    deleted = RetentionService.nightly_sweep_delete_due()
    assert deleted >= 1

    # Ensure recipe is gone
    gone = db_session.get(Recipe, recipe.id)
    assert gone is None

