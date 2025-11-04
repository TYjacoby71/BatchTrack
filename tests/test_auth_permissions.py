from uuid import uuid4
from flask import jsonify

from app.models import User, Organization, Role, Permission, SubscriptionTier
from app.utils.permissions import permission_required


def _create_org_with_permission(db_session):
    """Seed an organization, tier, role, and user wired with a unique permission."""
    suffix = uuid4().hex
    perm_name = f"feature.manage.{suffix}"

    permission = Permission(name=perm_name)
    db_session.add(permission)

    tier = SubscriptionTier(
        name=f"Tier-{suffix}",
        billing_provider='exempt',
        user_limit=5,
    )
    tier.permissions.append(permission)
    db_session.add(tier)
    db_session.flush()

    org = Organization(
        name=f"Org-{suffix}",
        subscription_tier_id=tier.id,
        billing_status='active',
    )
    db_session.add(org)
    db_session.flush()

    role = Role(name=f"Role-{suffix}", organization_id=org.id)
    role.permissions.append(permission)
    db_session.add(role)
    db_session.flush()

    user = User(
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        organization_id=org.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    user.assign_role(role)

    return perm_name, user, org


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def test_permission_required_allows_authorized_user(app, client, db_session):
    app.config['SKIP_PERMISSIONS'] = False

    with app.app_context():
        perm_name, user, _ = _create_org_with_permission(db_session)
        route_suffix = uuid4().hex

        endpoint = f"protected_{route_suffix}"

        @permission_required(perm_name)
        def _protected():
            return "ok", 200

        app.add_url_rule(
            f"/authz/protected/{route_suffix}",
            endpoint,
            _protected,
        )

    _login(client, user.id)
    response = client.get(f"/authz/protected/{route_suffix}")

    assert response.status_code == 200
    assert response.data == b"ok"


def test_permission_required_denies_user_without_permission(app, client, db_session):
    app.config['SKIP_PERMISSIONS'] = False

    with app.app_context():
        perm_name, privileged_user, org = _create_org_with_permission(db_session)

        # Create a second user in same org without the privileged role
        other_user = User(
            username=f"unauth_{uuid4().hex}",
            email=f"unauth_{uuid4().hex}@example.com",
            organization_id=org.id,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.commit()

        route_suffix = uuid4().hex

        @permission_required(perm_name)
        def _api_protected():
            return jsonify(success=True)

        app.add_url_rule(
            f"/authz/api/{route_suffix}",
            f"api_protected_{route_suffix}",
            _api_protected,
        )

    # Authenticate the unprivileged user
    _login(client, other_user.id)
    response = client.get(
        f"/authz/api/{route_suffix}",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 403
    assert response.is_json
    payload = response.get_json()
    assert payload["error"].startswith("Permission denied")

    # Control: privileged user should still pass
    _login(client, privileged_user.id)
    ok_response = client.get(
        f"/authz/api/{route_suffix}",
        headers={"Accept": "application/json"},
    )
    assert ok_response.status_code == 200


def test_permission_required_requires_authentication(app, client, db_session):
    app.config['SKIP_PERMISSIONS'] = False

    with app.app_context():
        perm_name, _, _ = _create_org_with_permission(db_session)
        route_suffix = uuid4().hex

        @permission_required(perm_name)
        def _api_route():
            return jsonify(success=True)

        app.add_url_rule(
            f"/authz/anon/{route_suffix}",
            f"anon_protected_{route_suffix}",
            _api_route,
        )

    response = client.get(
        f"/authz/anon/{route_suffix}",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()["error"] == "Authentication required"