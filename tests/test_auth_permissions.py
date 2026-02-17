from uuid import uuid4

from flask import jsonify
from flask_login import login_user, logout_user

from app.models import Organization, Permission, Role, SubscriptionTier, User
from app.utils.permissions import permission_required


def _create_org_with_permission(db_session):
    """Seed an organization, tier, role, and user wired with a unique permission."""
    suffix = uuid4().hex
    perm_name = f"feature.manage.{suffix}"

    permission = Permission(name=perm_name)
    db_session.add(permission)

    tier = SubscriptionTier(
        name=f"Tier-{suffix}",
        billing_provider="exempt",
        user_limit=5,
    )
    tier.permissions.append(permission)
    db_session.add(tier)
    db_session.flush()

    org = Organization(
        name=f"Org-{suffix}",
        subscription_tier_id=tier.id,
        billing_status="active",
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
    db_session.flush()

    user_id = user.id
    org_id = org.id

    from app.models.user_role_assignment import UserRoleAssignment

    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=role.id,
        organization_id=org_id,
        is_active=True,
    )
    db_session.add(assignment)
    db_session.commit()

    return perm_name, user_id, org_id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess.clear()
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_permission_required_allows_authorized_user(app, client, db_session):
    app.config["SKIP_PERMISSIONS"] = False

    with app.app_context():
        perm_name, user_id, _ = _create_org_with_permission(db_session)
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

    with client:
        _login(client, user_id)
        response = client.get(f"/authz/protected/{route_suffix}")

    assert response.status_code == 200
    assert response.data == b"ok"


def test_permission_required_denies_user_without_permission(app, client, db_session):
    app.config["SKIP_PERMISSIONS"] = False

    with app.app_context():
        perm_name, privileged_user_id, org_id = _create_org_with_permission(db_session)

        # Create a second user in same org without the privileged role
        other_user = User(
            username=f"unauth_{uuid4().hex}",
            email=f"unauth_{uuid4().hex}@example.com",
            organization_id=org_id,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.flush()
        other_user_id = other_user.id
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

    with app.app_context():
        privileged_user = db_session.get(User, privileged_user_id)
        assert privileged_user is not None
        assert privileged_user.has_permission(perm_name)
        from app.models.user_role_assignment import UserRoleAssignment

        assignments = UserRoleAssignment.query.filter_by(
            user_id=privileged_user_id, is_active=True
        ).all()
        assert assignments, "Role assignment should exist"

    # Authenticate the unprivileged user via request context
    other = db_session.get(User, other_user_id)
    with app.test_request_context(
        f"/authz/api/{route_suffix}", headers={"Accept": "application/json"}
    ):
        login_user(other)
        response = app.make_response(
            app.view_functions[f"api_protected_{route_suffix}"]()
        )
        logout_user()

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["error"] == "permission_denied"
    assert payload["permission"] == perm_name

    # Control: privileged user should still pass
    privileged = db_session.get(User, privileged_user_id)
    with app.test_request_context(
        f"/authz/api/{route_suffix}", headers={"Accept": "application/json"}
    ):
        login_user(privileged)
        ok_response = app.make_response(
            app.view_functions[f"api_protected_{route_suffix}"]()
        )
        logout_user()

    assert ok_response.status_code == 200, ok_response.get_json()


def test_permission_required_requires_authentication(app, client, db_session):
    app.config["SKIP_PERMISSIONS"] = False

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
