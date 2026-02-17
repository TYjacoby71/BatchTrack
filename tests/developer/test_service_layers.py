from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models import Organization, User
from app.models.global_item import GlobalItem
from app.models.subscription_tier import SubscriptionTier
from app.services.developer.organization_service import OrganizationService
from app.services.developer.reference_data_service import ReferenceDataService
from app.services.developer.user_service import UserService


@pytest.mark.usefixtures("app_context")
class TestOrganizationService:
    def test_build_available_tiers_includes_new_tier(self):
        tier = SubscriptionTier(name="Service Tier A", user_limit=5)
        db.session.add(tier)
        db.session.commit()

        tiers = OrganizationService.build_available_tiers()

        assert str(tier.id) in tiers
        assert tiers[str(tier.id)]["name"] == "Service Tier A"

    def test_create_org_with_owner_persists_entities(self):
        tier = SubscriptionTier(name="Owner Tier", user_limit=5)
        db.session.add(tier)
        db.session.commit()

        form_data = {
            "name": "Service Org",
            "username": f"owner_{uuid.uuid4().hex[:8]}",
            "email": "owner@example.com",
            "password": "TempPass!234",
            "subscription_tier": str(tier.id),
        }

        success, org, message = OrganizationService.create_organization_with_owner(
            form_data
        )

        assert success, message
        assert org is not None
        owner = User.query.filter_by(username=form_data["username"]).first()
        assert owner is not None
        assert owner.organization_id == org.id
        # The role assignment happens asynchronously; ensure the legacy flag is set.
        assert owner._is_organization_owner is True  # pylint: disable=protected-access


@pytest.mark.usefixtures("app_context")
class TestUserService:
    def test_toggle_user_active_flips_state(self):
        org = Organization(name="Toggle Org")
        user = User(
            username=f"customer_{uuid.uuid4().hex[:6]}",
            email="toggle@example.com",
            organization=org,
            user_type="customer",
            is_active=True,
        )
        db.session.add_all([org, user])
        db.session.commit()

        success, message = UserService.toggle_user_active(user)

        assert success
        assert "deactivated" in message
        assert user.is_active is False

    def test_serialize_user_includes_expected_fields(self):
        org = Organization(name="Serialize Org")
        user = User(
            username=f"serialize_{uuid.uuid4().hex[:6]}",
            email="serialize@example.com",
            organization=org,
            user_type="customer",
            is_active=True,
        )
        db.session.add_all([org, user])
        db.session.commit()

        payload = UserService.serialize_user(user)

        assert payload["username"] == user.username
        assert payload["organization_id"] == org.id
        assert payload["is_active"] is True


@pytest.mark.usefixtures("app_context")
class TestReferenceDataService:
    def test_load_curated_lists_falls_back_to_defaults_with_db_values(
        self, monkeypatch
    ):
        # Remove any persisted settings so the DB merge path executes.
        monkeypatch.setattr(
            ReferenceDataService,
            "DEFAULTS",
            ReferenceDataService.DEFAULTS.copy(),
            raising=False,
        )
        monkeypatch.setattr(
            "app.services.developer.reference_data_service.read_json_file",
            lambda *_, **__: {},
        )

        custom_item = GlobalItem(
            name="Curated Container",
            item_type="container",
            container_material="Bamboo",
            container_type="Decanter",
            container_style="Ornate",
            container_color="Rose Gold",
        )
        db.session.add(custom_item)
        db.session.commit()

        lists = ReferenceDataService.load_curated_container_lists()

        assert "Bamboo" in lists["materials"]
        assert "Decanter" in lists["types"]
        assert "Ornate" in lists["styles"]
        assert "Rose Gold" in lists["colors"]

    def test_save_curated_lists_writes_settings(self, monkeypatch):
        captured = {}

        def fake_read(*args, **kwargs):
            return {}

        def fake_write(path, data):
            captured["payload"] = data

        monkeypatch.setattr(
            "app.services.developer.reference_data_service.read_json_file", fake_read
        )
        monkeypatch.setattr(
            "app.services.developer.reference_data_service.write_json_file", fake_write
        )

        ReferenceDataService.save_curated_container_lists(
            {
                "materials": ["Glass"],
                "types": ["Jar"],
                "styles": ["Modern"],
                "colors": ["Clear"],
            }
        )

        assert "payload" in captured
        assert captured["payload"]["container_management"]["curated_lists"][
            "materials"
        ] == ["Glass"]
