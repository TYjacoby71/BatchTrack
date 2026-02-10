import uuid

from app.extensions import db
from app.models.models import User, Organization


def _create_user(app):
    """Helper to create a user with a known password for session tests."""
    suffix = uuid.uuid4().hex[:8]
    username = f"session_user_{suffix}"
    password = "super-secret-pass"

    with app.app_context():
        from app.models.permission import Permission
        from app.models.role import Role
        from app.models.subscription_tier import SubscriptionTier

        org = Organization(name=f"Session Org {suffix}")
        db.session.add(org)
        db.session.flush()

        perm = Permission.query.filter_by(name='dashboard.view').first()
        if not perm:
            perm = Permission(name='dashboard.view', description='View dashboard')
            db.session.add(perm)
            db.session.flush()

        tier = SubscriptionTier(
            name=f"Session Tier {suffix}",
            billing_provider='exempt',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()
        tier.permissions.append(perm)
        org.subscription_tier_id = tier.id

        user = User(
            username=username,
            email=f"{username}@example.com",
            organization_id=org.id,
            is_active=True,
            is_verified=True,
            user_type="customer",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if org_owner_role:
            user.assign_role(org_owner_role)

    return username, password


def test_subsequent_login_invalidates_existing_session(app):
    username, password = _create_user(app)

    first_client = app.test_client()
    second_client = app.test_client()

    response = first_client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302

    # Confirm authenticated access works with the first session.
    authed_response = first_client.get("/auth-check", headers={"Accept": "application/json"})
    assert authed_response.status_code == 200

    response = second_client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302

    # The first session should now be invalidated and receive a 401 JSON response.
    invalidated = first_client.get("/auth-check", headers={"Accept": "application/json"})
    assert invalidated.status_code == 401
    assert invalidated.get_json().get("error") == "Authentication required"

    # The second session remains valid.
    still_valid = second_client.get("/auth-check", headers={"Accept": "application/json"})
    assert still_valid.status_code == 200
