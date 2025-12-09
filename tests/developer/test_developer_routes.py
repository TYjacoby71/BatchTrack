from __future__ import annotations

import uuid

from app.extensions import db
from app.models import Organization, User
from app.models.subscription_tier import SubscriptionTier


def _login_as_developer(client, developer_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(developer_user.id)


def _create_customer(app):
    with app.app_context():
        org = Organization(name=f"Customer Org {uuid.uuid4().hex[:6]}")
        user = User(
            username=f"customer_{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:6]}@example.com",
            organization=org,
            user_type="customer",
            is_active=True,
        )
        db.session.add_all([org, user])
        db.session.commit()
        return user.id


def _create_subscription_tier(app):
    with app.app_context():
        tier = SubscriptionTier(name=f"Dev Tier {uuid.uuid4().hex[:6]}", user_limit=5)
        db.session.add(tier)
        db.session.commit()
        return tier.id


def test_users_page_renders(client, developer_user):
    _login_as_developer(client, developer_user)
    resp = client.get("/developer/users")
    assert resp.status_code == 200


def test_toggle_user_active_endpoint(client, developer_user, app):
    _login_as_developer(client, developer_user)
    customer_id = _create_customer(app)

    resp = client.post(f"/developer/users/{customer_id}/toggle-active", follow_redirects=False)

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(User, customer_id).is_active is False


def test_user_update_api(client, developer_user, app):
    _login_as_developer(client, developer_user)
    customer_id = _create_customer(app)

    payload = {
        "user_id": customer_id,
        "first_name": "Updated",
        "last_name": "Customer",
        "email": "updated@example.com",
        "phone": "555-0100",
        "user_type": "customer",
        "is_active": True,
    }
    resp = client.post("/developer/api/user/update", json=payload)

    assert resp.status_code == 200
    with app.app_context():
        user = db.session.get(User, customer_id)
        assert user.first_name == "Updated"
        assert user.email == "updated@example.com"


def test_container_options_api(client, developer_user):
    _login_as_developer(client, developer_user)
    resp = client.get("/developer/api/container-options")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["success"] is True
    assert all(key in data["options"] for key in ("materials", "types", "styles", "colors"))


def test_organizations_page_renders(client, developer_user):
    _login_as_developer(client, developer_user)
    resp = client.get("/developer/organizations")
    assert resp.status_code == 200


def test_create_organization_flow(client, developer_user, app):
    _login_as_developer(client, developer_user)
    tier_id = _create_subscription_tier(app)
    form = {
        "name": "RouteOrg",
        "subscription_tier": str(tier_id),
        "creation_reason": "testing",
        "notes": "",
        "username": f"route_owner_{uuid.uuid4().hex[:6]}",
        "email": f"route_owner_{uuid.uuid4().hex[:6]}@example.com",
        "first_name": "Route",
        "last_name": "Owner",
        "password": "TempPass!123",
        "phone": "",
    }

    resp = client.post("/developer/organizations/create", data=form, follow_redirects=False)

    assert resp.status_code == 302
    with client.application.app_context():
        assert User.query.filter_by(username=form["username"]).first() is not None

