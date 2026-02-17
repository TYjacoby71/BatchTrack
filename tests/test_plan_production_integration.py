import json

from app.extensions import db
from app.models.models import User


def _api(client, app, path, payload):
    # Ensure an authenticated client session by setting flask-login keys
    with app.app_context():
        user = User.query.first()
        if not user:
            from app.models import Organization
            from app.models.permission import Permission
            from app.models.role import Role
            from app.models.subscription_tier import SubscriptionTier

            org = Organization(name="Test Org")
            db.session.add(org)
            db.session.flush()

            perm = Permission.query.filter_by(name="batches.create").first()
            if not perm:
                perm = Permission(
                    name="batches.create", description="Start production batches"
                )
                db.session.add(perm)
                db.session.flush()

            tier = SubscriptionTier(
                name="Integration Tier", billing_provider="exempt", user_limit=5
            )
            db.session.add(tier)
            db.session.flush()
            tier.permissions.append(perm)
            org.subscription_tier_id = tier.id

            user = User(
                username="apitester",
                email="apitester@example.com",
                is_active=True,
                is_verified=True,
                organization_id=org.id,
            )
            db.session.add(user)
            db.session.commit()
            org_owner_role = Role.query.filter_by(
                name="organization_owner", is_system_role=True
            ).first()
            if org_owner_role:
                user.assign_role(org_owner_role)
        user_id = user.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Accept": "application/json"},
    )


def test_plan_start_finish_non_portioned(app, client):
    app.config["SKIP_PERMISSIONS"] = True
    # Arrange: create a simple recipe
    from app.models import Organization, Recipe, User

    with app.app_context():
        # Get or create user with organization
        user = User.query.first()
        if not user:
            org = Organization(name="Test Org")
            db.session.add(org)
            db.session.flush()
            user = User(
                username="apitester",
                email="apitester@example.com",
                is_active=True,
                is_verified=True,
                organization_id=org.id,
            )
            db.session.add(user)
            db.session.commit()

        r = Recipe(
            name="Simple Syrup",
            predicted_yield=10.0,
            predicted_yield_unit="oz",
            category_id=1,
            organization_id=user.organization_id,
        )
        db.session.add(r)
        db.session.commit()
        recipe_id = r.id

    # Act: start batch with no portioning
    resp = _api(
        client,
        app,
        "/batches/api/start-batch",
        {
            "recipe_id": recipe_id,
            "scale": 1,
            "batch_type": "ingredient",
            "notes": "",
            "requires_containers": False,
            "containers": [],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    batch_id = data["batch_id"]

    # Assert: batch in progress page renders and shows projected yield
    page = client.get(f"/batches/in-progress/{batch_id}")
    assert page.status_code == 200
    assert b"Projected Yield" in page.data

    # Finish batch
    finish = client.post(
        f"/batches/finish-batch/{batch_id}/complete",
        data={"final_quantity": "10", "output_unit": "oz", "output_type": "ingredient"},
    )
    assert finish.status_code in (200, 302)

    # View record page
    rec = client.get(f"/batches/{batch_id}")
    assert rec.status_code in (200, 302)


def test_plan_start_finish_portioned(app, client):
    app.config["SKIP_PERMISSIONS"] = True
    # Arrange: create a portioned recipe
    from app.models import Organization, Recipe, User

    with app.app_context():
        # Get or create user with organization
        user = User.query.first()
        if not user:
            org = Organization(name="Test Org")
            db.session.add(org)
            db.session.flush()
            user = User(
                username="apitester",
                email="apitester@example.com",
                is_active=True,
                is_verified=True,
                organization_id=org.id,
            )
            db.session.add(user)
            db.session.commit()

        r = Recipe(
            name="Goat Milk Soap",
            predicted_yield=10.0,
            predicted_yield_unit="oz",
            category_id=1,
            organization_id=user.organization_id,
            portioning_data={
                "is_portioned": True,
                "portion_name": "bars",
                "portion_count": 20,
            },
            is_portioned=True,
            portion_name="bars",
            portion_count=20,
        )
        db.session.add(r)
        db.session.commit()
        recipe_id = r.id

    # Act: start batch with flat portion fields
    resp = _api(
        client,
        app,
        "/batches/api/start-batch",
        {
            "recipe_id": recipe_id,
            "scale": 1,
            "batch_type": "product",
            "notes": "",
            "requires_containers": False,
            "containers": [],
            "is_portioned": True,
            "portion_name": "bars",
            "portion_count": 20,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    batch_id = data["batch_id"]

    # Assert: batch in progress shows projected portions
    page = client.get(f"/batches/in-progress/{batch_id}")
    assert page.status_code == 200
    assert b"Projected Portions" in page.data
    assert b"bars" in page.data

    # Finish batch with final portions
    finish = client.post(
        f"/batches/finish-batch/{batch_id}/complete",
        data={
            "final_quantity": "10",
            "output_unit": "oz",
            "output_type": "product",
            "product_id": "",
            "variant_id": "",
            "final_portions": "20",
        },
    )
    assert finish.status_code in (200, 302)

    # View record page after completion or redirect fallback
    rec = client.get(f"/batches/{batch_id}")
    assert rec.status_code in (200, 302)
