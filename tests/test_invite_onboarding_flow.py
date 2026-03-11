"""Invite verification and setup onboarding flow tests."""

from __future__ import annotations

import uuid

from flask_login import login_user

from app.extensions import db
from app.models.models import Organization, Role, SubscriptionTier, User
from app.services.email_service import EmailService
from app.services.user_invite_service import UserInviteService
from app.utils.timezone_utils import TimezoneUtils


def _mk_org_with_owner(app):
    with app.app_context():
        tier = SubscriptionTier(
            name=f"Invite Tier {uuid.uuid4().hex[:6]}",
            user_limit=5,
            billing_provider="exempt",
        )
        db.session.add(tier)
        db.session.flush()
        org = Organization(name=f"Invite Org {uuid.uuid4().hex[:6]}", is_active=True)
        org.subscription_tier_id = tier.id
        db.session.add(org)
        db.session.flush()
        owner = User(
            username=f"owner_{uuid.uuid4().hex[:8]}",
            email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
            organization_id=org.id,
            user_type="customer",
            is_active=True,
        )
        owner.set_password("owner-pass-123")
        db.session.add(owner)
        role = Role(
            name=f"qa_invited_{uuid.uuid4().hex[:8]}",
            organization_id=org.id,
            is_active=True,
            is_system_role=False,
        )
        db.session.add(role)
        db.session.commit()
        return org.id, owner.id, role.id


def test_invite_user_sends_verification_email_with_invite_setup_next(app, monkeypatch):
    org_id, owner_id, role_id = _mk_org_with_owner(app)
    sent = {}

    monkeypatch.setattr(EmailService, "is_configured", staticmethod(lambda: True))

    def _fake_send(email, token, user_name=None, next_path=None):
        sent["email"] = email
        sent["token"] = token
        sent["next_path"] = next_path
        return True

    monkeypatch.setattr(
        EmailService, "send_verification_email", staticmethod(_fake_send)
    )

    with app.app_context():
        org = db.session.get(Organization, org_id)
        owner = db.session.get(User, owner_id)
        with app.test_request_context("/organization/invite-user"):
            login_user(owner)
            result = UserInviteService.invite_user(
                organization=org,
                email="invited@example.com",
                role_id=role_id,
                first_name="Invite",
                last_name="Member",
            )
        assert result.success is True
        invited_user = User.find_by_email("invited@example.com")
        assert invited_user is not None
        assert invited_user.email_verification_token
        assert invited_user.password_reset_token
        assert sent["email"] == "invited@example.com"
        assert sent["token"] == invited_user.email_verification_token
        assert sent["next_path"].startswith("/onboarding/invite-setup/")


def test_invite_setup_route_updates_profile_and_password(app, client):
    with app.app_context():
        org = Organization(name=f"Setup Org {uuid.uuid4().hex[:6]}", is_active=True)
        db.session.add(org)
        db.session.flush()
        user = User(
            username=f"setup_{uuid.uuid4().hex[:8]}",
            email=f"setup_{uuid.uuid4().hex[:8]}@example.com",
            user_type="team_member",
            organization_id=org.id,
            is_active=True,
            email_verified=True,
        )
        user.set_password("old-pass-123")
        user.password_reset_token = EmailService.generate_reset_token(999)
        user.password_reset_sent_at = TimezoneUtils.utc_now()
        db.session.add(user)
        db.session.commit()
        token = user.password_reset_token
        email = user.email

    get_response = client.get(f"/onboarding/invite-setup/{token}")
    assert get_response.status_code == 200
    assert "Finish your BatchTrack setup" in get_response.get_data(as_text=True)

    post_response = client.post(
        f"/onboarding/invite-setup/{token}",
        data={
            "first_name": "New",
            "last_name": "Invitee",
            "user_phone": "555-0009",
            "username": "invite_member_new",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
        follow_redirects=False,
    )
    assert post_response.status_code == 302
    assert post_response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed = User.find_by_email(email)
        assert refreshed is not None
        assert refreshed.first_name == "New"
        assert refreshed.last_name == "Invitee"
        assert refreshed.phone == "555-0009"
        assert refreshed.username == "invite_member_new"
        assert refreshed.password_reset_token is None
        assert refreshed.check_password("newpass123") is True
