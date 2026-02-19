"""Auth email-security behavior tests.

Synopsis:
Covers prompt/required/off verification modes and password-reset token flows.

Glossary:
- Prompt mode: Unverified users can proceed while being nudged to verify.
- Required mode: Unverified users are blocked from login.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.extensions import db
from app.models import Organization, User
from app.utils.timezone_utils import TimezoneUtils


# --- Create user helper ---
# Purpose: Build test users with explicit verification state and known password.
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


# --- Prompt mode login ---
# Purpose: Verify unverified accounts can log in and receive verification prompts in prompt mode.
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
    assert (
        "/dashboard" in response.headers["Location"]
        or "/user_dashboard" in response.headers["Location"]
    )

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verification_token
        assert refreshed.email_verification_sent_at is not None

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


# --- Prompt mode age reminder modal ---
# Purpose: Verify old unverified accounts can log in and receive forced-send modal context.
def test_prompt_mode_old_unverified_accounts_queue_post_login_modal(
    client, app, monkeypatch
):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False
    app.config["AUTH_EMAIL_FORCE_REQUIRED_AFTER_DAYS"] = 10

    with app.app_context():
        user = _create_user(
            username=f"legacy_{uuid.uuid4().hex[:6]}",
            email=f"legacy_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        user.created_at = TimezoneUtils.utc_now() - timedelta(days=12)
        db.session.commit()
        username = user.username

    monkeypatch.setattr(
        "app.blueprints.auth.login_routes.EmailService.send_verification_email",
        lambda *args, **kwargs: True,
    )

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/dashboard" in location or "/user_dashboard" in location

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None
        modal_payload = sess.get("verification_required_modal")
        assert modal_payload is not None
        assert modal_payload.get("sent") is True
        assert modal_payload.get("grace_days") == 10
        flashes = [message for _category, message in sess.get("_flashes", [])]
        assert any("older than 10 days" in msg for msg in flashes)

# --- Forced resend modal rendering ---
# Purpose: Verify forced-lock query flags render modal guidance on resend page.
def test_resend_verification_renders_forced_age_modal(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    response = client.get(
        "/auth/resend-verification"
        "?forced=1&sent=1&age_days=12&grace_days=10&email=legacy_user@example.com"
    )
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'id="forcedVerificationModal"' in html
    assert "legacy_user@example.com" in html
    assert "has passed the" in html
    assert "10-day verification window" in html


# --- Naive verification timestamp compatibility ---
# Purpose: Verify login flow handles legacy naive verification timestamps without crashing.
def test_login_handles_naive_verification_timestamp_without_send_crash(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"naive_verify_{uuid.uuid4().hex[:6]}",
            email=f"naive_verify_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        user.email_verification_token = f"legacy-{uuid.uuid4().hex}"
        user.email_verification_sent_at = TimezoneUtils.utc_now().replace(tzinfo=None)
        db.session.commit()
        username = user.username

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"] or "/user_dashboard" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


# --- Authenticated resend messaging ---
# Purpose: Verify authenticated resend uses specific user-facing confirmation copy.
def test_authenticated_resend_verification_uses_specific_message(client, app, monkeypatch):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"auth_resend_{uuid.uuid4().hex[:6]}",
            email=f"auth_resend_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username
        email = user.email

    login_response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    monkeypatch.setattr(
        "app.blueprints.auth.verification_routes.EmailService.send_verification_email",
        lambda *args, **kwargs: True,
    )

    resend_response = client.post(
        "/auth/resend-verification",
        data={"email": email, "next": "/dashboard"},
        follow_redirects=False,
    )
    assert resend_response.status_code == 302
    assert "/dashboard" in resend_response.headers["Location"]

    with client.session_transaction() as sess:
        flashes = [message for _category, message in sess.get("_flashes", [])]
        assert any(f"Verification email sent to {email}." in msg for msg in flashes)
        assert all(
            "If an account with that email exists and is unverified" not in msg
            for msg in flashes
        )


# --- Email identifier login ---
# Purpose: Verify login accepts email as credential identifier in addition to username.
def test_login_accepts_email_identifier(client, app):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"email_login_{uuid.uuid4().hex[:6]}",
            email=f"email_login_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=True,
        )
        email = user.email

    response = client.post(
        "/auth/login",
        data={"username": email, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "dashboard" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


# --- Provider fallback login ---
# Purpose: Verify auth-email features auto-relax when provider-required mode lacks credentials.
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
    assert (
        "/dashboard" in response.headers["Location"]
        or "/user_dashboard" in response.headers["Location"]
    )

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verification_token in (None, "")
        assert refreshed.email_verification_sent_at is None

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None


# --- Required mode login ---
# Purpose: Verify strict mode blocks unverified accounts and redirects to resend verification.
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


# --- Required mode send-failure messaging ---
# Purpose: Verify required-mode login does not claim delivery when verification send fails.
def test_required_mode_login_message_handles_verification_send_failure(client, app, monkeypatch):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "required"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"required_fail_{uuid.uuid4().hex[:6]}",
            email=f"required_fail_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username

    monkeypatch.setattr(
        "app.blueprints.auth.login_routes.EmailService.send_verification_email",
        lambda *args, **kwargs: False,
    )

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/auth/resend-verification" in response.headers["Location"]

    with client.session_transaction() as sess:
        flashes = [message for _category, message in sess.get("_flashes", [])]
        assert any("could not send a verification email" in msg for msg in flashes)
        assert all("We sent you a verification link." not in msg for msg in flashes)

    with app.app_context():
        refreshed = User.query.filter_by(username=username).first()
        assert refreshed is not None
        assert refreshed.email_verification_token is None
        assert refreshed.email_verification_sent_at is None


# --- Prompt mode send-failure messaging ---
# Purpose: Verify prompt-mode login reports delivery failure accurately when send fails.
def test_prompt_mode_login_message_handles_verification_send_failure(
    client, app, monkeypatch
):
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False

    with app.app_context():
        user = _create_user(
            username=f"prompt_fail_{uuid.uuid4().hex[:6]}",
            email=f"prompt_fail_{uuid.uuid4().hex[:6]}@example.com",
            password="pass-12345",
            verified=False,
        )
        username = user.username

    monkeypatch.setattr(
        "app.blueprints.auth.login_routes.EmailService.send_verification_email",
        lambda *args, **kwargs: False,
    )

    response = client.post(
        "/auth/login",
        data={"username": username, "password": "pass-12345"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"] or "/user_dashboard" in response.headers["Location"]

    with client.session_transaction() as sess:
        flashes = [message for _category, message in sess.get("_flashes", [])]
        assert any("could not send a verification email" in msg for msg in flashes)
        assert all("A verification link was sent." not in msg for msg in flashes)
        assert sess.get("_user_id") is not None

    with app.app_context():
        refreshed = User.query.filter_by(username=username).first()
        assert refreshed is not None
        assert refreshed.email_verification_token is None
        assert refreshed.email_verification_sent_at is None


# --- Forgot/reset flow ---
# Purpose: Verify reset token issuance, password update, and successful relogin path.
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


# --- Reset implies verification ---
# Purpose: Ensure token-backed reset marks mailbox as verified for previously unverified users.
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
        data={
            "password": "final-password-123",
            "confirm_password": "final-password-123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed = User.query.filter_by(email=email).first()
        assert refreshed is not None
        assert refreshed.email_verified is True
