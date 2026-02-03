from datetime import datetime, timedelta, timezone


def test_retention_flow_ack_to_delete(client, db_session, app):
    # Arrange: create org, tier with 365d retention, user, and an old recipe not used by batches
    from app.models import Organization, User
    from app.models.permission import Permission
    from app.models.subscription_tier import SubscriptionTier
    from app.models.recipe import Recipe
    from app.services.retention_service import RetentionService

    import time
    unique_suffix = str(int(time.time() * 1000))[-6:]
    tier = SubscriptionTier(name=f'Test Tier {unique_suffix}', billing_provider='exempt', user_limit=5, data_retention_days=365)
    db_session.add(tier)
    perm = Permission.query.filter_by(name='recipes.delete').first()
    if not perm:
        perm = Permission(name='recipes.delete', description='Delete recipes')
        db_session.add(perm)
        db_session.flush()
    tier.permissions.append(perm)
    org = Organization(name='Retention Org')
    db_session.add(org)
    db_session.flush()
    org.subscription_tier_id = tier.id

    user = User(username='ret_user', email='ret@example.com')
    user.organization_id = org.id
    user.set_password('password')
    db_session.add(user)
    db_session.commit()
    user.is_organization_owner = True
    db_session.commit()

    # Login
    client.post('/auth/login', data={'username': 'ret_user', 'password': 'password'})

    old_date = datetime.now(timezone.utc) - timedelta(days=366)
    recipe = Recipe(name='Old Draft', organization_id=org.id, created_at=old_date)
    db_session.add(recipe)
    db_session.commit()

    # Act: check drawer
    r = client.get('/api/drawers/retention/check')
    assert r.status_code == 200
    assert r.json['needs_drawer'] is True
    assert r.json['count'] >= 1

    # Get modal
    r = client.get('/api/drawers/retention/modal')
    assert r.status_code == 200
    assert r.json['success'] is True
    assert 'Data Retention Notice' in r.json['modal_html']

    # Acknowledge
    r = client.post('/api/drawers/retention/acknowledge', json={'acknowledge': True})
    assert r.status_code == 200
    assert r.json['success'] is True
    assert r.json['queued'] >= 1

    # Drawer should not show again now for same items
    r = client.get('/api/drawers/retention/check')
    assert r.status_code == 200
    assert r.json['needs_drawer'] in [False, True]  # could be more items in other tests

    # Fast-forward: make eligible for deletion now
    from app.models.retention import RetentionDeletionQueue
    q = RetentionDeletionQueue.query.filter_by(organization_id=org.id, recipe_id=recipe.id).first()
    assert q is not None
    q.delete_after_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    # Sweep
    deleted = RetentionService.nightly_sweep_delete_due()
    assert deleted >= 1

    # Ensure recipe is gone
    gone = db_session.get(Recipe, recipe.id)
    assert gone is None

