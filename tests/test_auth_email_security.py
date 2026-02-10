from __future__ import annotations

import uuid

from app.extensions import db
from app.models import Organization, User
from app.utils.timezone_utils import TimezoneUtils


def _create_user(*, username: str, email: str, password: str, verified: bool) -> User:
    org = Organization(name=f"Auth Org {uuid.uuid4().hex[:8]}")
    db.session.add(org)
    db.session.flush()

    user = User(
        username=username,
        email=email,
        organization_id=org.id,
        is_active=True,
        is_verified=verified,
        user_type="customer",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def test_login_prompts_unverified_email_without_blocking(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"unverified_{uuid.uuid4().hex[:6]}",
            email=f"unverified_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username
        email = user.email

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verification_token
        assert refreshed.email_verification_sent_at is not None

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


def test_login_falls_back_to_legacy_when_email_provider_missing(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = True
    app.config["EMAIL_SMTP_ALLOW_NO_AUTH"] = False
    app.config["MAIL_USERNAME"] = None
    app.config["MAIL_PASSWORD"] = None

    with app.app_context():
        user = _create_user(
            username=f"legacy_{uuid.uuid4().hex[:6]}",
            email=f"legacy_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username
        email = user.email

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verification_token in (None, "")
        assert refreshed.email_verification_sent_at is None

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


def test_login_blocks_unverified_when_required_mode(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "required"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"required_{uuid.uuid4().hex[:6]}",
            email=f"required_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/auth/resend-verification" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is None


def test_forgot_password_and_reset_flow(client, app):
    app.config["AUTH_PASSWORD_RESET_ENABLED"] = True
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"verified_{uuid.uuid4().hex[:6]}",
            email=f"verified_{uuid.uuid4().hex[:6]}@example.com",
            password="old-password",
            verified=True,
        )
        user_email = user.email
        username = user.username

    forgot_response = client.post(
        "/auth/forgot-password",
        data={"email": user_email},
        follow_redirects=False,
    )
    assert forgot_response.status_code == 302
    assert forgot_response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed = User.query.filter_by(email=user_email).first()
        assert refreshed is not None
        token = refreshed.password_reset_token
        assert token
        assert refreshed.password_reset_sent_at is not None

    reset_response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "new-password-123", "confirm_password": "new-password-123"},
        follow_redirects=False,
    )
    assert reset_response.status_code == 302
    assert reset_response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed = User.query.filter_by(email=user_email).first()
        assert refreshed is not None
        assert refreshed.password_reset_token is None
        assert refreshed.password_reset_sent_at is None
        assert refreshed.check_password("new-password-123")
        assert not refreshed.check_password("old-password")

    login_response = client.post(
        "/auth/login",
        data={"username": username, "password": "new-password-123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302
    assert "/auth/resend-verification" not in login_response.headers["Location"]


def test_reset_link_verifies_email_for_unverified_account(client, app):
    with app.app_context():
        user = _create_user(
            username=f"invite_{uuid.uuid4().hex[:6]}",
            email=f"invite_{uuid.uuid4().hex[:6]}@example.com",
            password="temp-password",
            verified=False,
        )
        user.password_reset_token = f"token-{uuid.uuid4().hex}"
        user.password_reset_sent_at = TimezoneUtils.utc_now()
        db.session.commit()
        token = user.password_reset_token
        email = user.email

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "final-password-123", "confirm_password": "final-password-123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verified is True
