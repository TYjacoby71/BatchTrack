"""Signup completion tracking regression tests."""

from __future__ import annotations

import uuid

from app.extensions import db
from app.models.domain_event import DomainEvent
from app.models.models import User
from app.services.email_service import EmailService


def test_quick_signup_emits_free_and_account_created_events(app, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(EmailService, "should_issue_verification_tokens", lambda: False)

    email = f"quick-{uuid.uuid4().hex[:10]}@example.com"
    signup_source = "recipe_library_cta"
    response = client.post(
        "/auth/quick-signup",
        data={
            "first_name": "Quick",
            "last_name": "Signup",
            "email": email,
            "password": "quickpass123",
            "next": "/inventory",
            "source": signup_source,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        created_user = User.query.filter_by(email=email).first()
        assert created_user is not None
        assert created_user.first_name == "Quick"
        assert created_user.last_name == "Signup"
        assert created_user.organization is not None
        assert created_user.organization.tier is not None

        for event_name in (
            "free_account_created",
            "account_created",
            "signup_completed",
        ):
            event = (
                DomainEvent.query.filter_by(
                    event_name=event_name,
                    user_id=created_user.id,
                )
                .order_by(DomainEvent.id.desc())
                .first()
            )
            assert event is not None
            props = event.properties or {}
            assert props.get("signup_flow") == "quick_signup"
            assert props.get("signup_source") == signup_source
            assert props.get("purchase_completed") is False
            assert props.get("used_promo_code") is False


def test_quick_signup_blocks_existing_email_and_keeps_prefill(app, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(EmailService, "should_issue_verification_tokens", lambda: False)
    existing_email = "quick-existing@example.com"
    with app.app_context():
        existing_user = User(
            username=f"existing-{uuid.uuid4().hex[:8]}",
            email=existing_email,
            user_type="developer",
            is_active=True,
        )
        existing_user.set_password("existing-pass-123")
        db.session.add(existing_user)
        db.session.commit()

    response = client.post(
        "/auth/quick-signup",
        data={
            "first_name": "Keep",
            "last_name": "State",
            "email": "QUICK-EXISTING@example.com",
            "password": "quickpass123",
            "next": "/inventory",
            "source": "quick_signup",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "An account with that email already exists. Please log in instead." in html
    assert 'value="Keep"' in html
    assert 'value="State"' in html
    assert 'value="quick-existing@example.com"' in html
