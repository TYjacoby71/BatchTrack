"""Signup completion tracking regression tests."""

from __future__ import annotations

import uuid

from app.models.domain_event import DomainEvent
from app.models.models import User
from app.services.email_service import EmailService


def test_quick_signup_emits_signup_completed_event(app, monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(
        EmailService, "should_issue_verification_tokens", lambda: False
    )

    email = f"quick-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/auth/quick-signup",
        data={
            "name": "Quick Signup",
            "email": email,
            "password": "quickpass123",
            "next": "/inventory",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        created_user = User.query.filter_by(email=email).first()
        assert created_user is not None

        event = (
            DomainEvent.query.filter_by(
                event_name="signup_completed",
                user_id=created_user.id,
            )
            .order_by(DomainEvent.id.desc())
            .first()
        )
        assert event is not None
        props = event.properties or {}
        assert props.get("signup_flow") == "quick_signup"
        assert props.get("purchase_completed") is False
        assert props.get("used_promo_code") is False
