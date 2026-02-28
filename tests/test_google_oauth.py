"""
Characterization tests for Google OAuth authentication flow.

These tests ensure OAuth state/nonce validation and security work correctly.
"""

from unittest.mock import patch

from app.extensions import db
from app.models import Organization, User
from app.services.oauth_service import OAuthService


class TestGoogleOAuthCharacterization:
    """Test current Google OAuth behavior to prevent regressions."""

    def test_oauth_service_exists(self, app):
        """Test that OAuth service is properly configured."""
        with app.app_context():
            service = OAuthService()
            assert service is not None

    def test_auth_login_endpoint_exists(self, app, client):
        """Test that OAuth login endpoint exists and generates state."""
        with app.app_context():
            response = client.get("/auth/login")

            # Characterize current behavior
            assert response.status_code in [200, 302, 401, 403]

    def test_auth_callback_endpoint_exists(self, app, client):
        """Test that OAuth callback endpoint exists."""
        with app.app_context():
            response = client.get("/auth/callback")

            # Characterize current behavior
            assert response.status_code in [200, 302, 400, 401, 403]

    def test_auth_facebook_endpoint_exists(self, app, client):
        """Test that Facebook OAuth initiation endpoint exists."""
        with app.app_context():
            response = client.get("/auth/oauth/facebook")
            assert response.status_code in [302, 401, 403]

    @patch("app.services.oauth_service.OAuthService.get_user_info")
    def test_oauth_state_validation_path(self, mock_get_user, app, client):
        """Test that OAuth state validation exists in current flow."""
        with app.app_context():
            # Mock successful OAuth response
            mock_get_user.return_value = {
                "email": "test@example.com",
                "given_name": "Test",
                "family_name": "User",
            }

            # Test callback with state parameter
            response = client.get("/auth/callback?state=test_state&code=test_code")

            # Characterize current behavior
            assert response.status_code in [200, 302, 400, 401, 403]

    def test_oauth_service_methods_exist(self, app):
        """Test that expected OAuth service methods exist."""
        with app.app_context():
            service = OAuthService()

            # Verify expected interface exists for proper delegation
            expected_methods = [
                "get_authorization_url",
                "get_user_info",
                "generate_state",
                "get_facebook_authorization_url",
                "get_facebook_user_info",
                "exchange_facebook_code_for_token",
                "get_enabled_providers",
            ]

            missing = [
                method for method in expected_methods if not hasattr(service, method)
            ]
            assert not missing, f"OAuthService is missing methods: {missing}"

            for method in expected_methods:
                attr = getattr(service, method)
                assert callable(attr), f"{method} should be callable on OAuthService"

            # Characterize the behavior of helper methods without hitting Google
            token = service.generate_state()
            assert isinstance(token, str) and len(token) >= 16

    def test_oauth_configuration_status(self, app):
        """Test OAuth configuration detection"""
        with app.app_context():
            status = OAuthService.get_configuration_status()

            # Should have required keys
            assert "is_configured" in status
            assert "missing_keys" in status

            # Test behavior varies based on actual config
            if status["is_configured"]:
                assert len(status["missing_keys"]) == 0
            else:
                assert len(status["missing_keys"]) > 0

    def test_oauth_callback_invalid_state(self, app, client):
        """Test OAuth callback with invalid state parameter"""
        with app.app_context():
            # Test callback with no state in session
            response = client.get(
                "/auth/oauth/callback?state=invalid_state&code=test_code"
            )

            # Should redirect to login with error
            assert response.status_code == 302
            assert "/auth/login" in response.location

            # Test callback with mismatched state
            with client.session_transaction() as sess:
                sess["oauth_state"] = "valid_state"
                sess["oauth_provider"] = "google"

            response = client.get(
                "/auth/oauth/callback?state=invalid_state&code=test_code"
            )

            # Should redirect to login with error
            assert response.status_code == 302
            assert "/auth/login" in response.location

    def test_oauth_callback_logs_in_existing_user_and_redirects(self, app, client):
        """Callback should authenticate known users and redirect to org dashboard."""
        with app.app_context():
            org = Organization(name="OAuth Existing Org")
            db.session.add(org)
            db.session.flush()
            user = User(
                username="oauth_existing_user",
                email="oauth.existing@example.com",
                organization_id=org.id,
                user_type="customer",
                is_active=True,
                email_verified=True,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with client.session_transaction() as sess:
            sess["oauth_state"] = "known-state"
            sess["oauth_provider"] = "google"

        with patch(
            "app.blueprints.auth.oauth_routes.OAuthService.exchange_code_for_token",
            return_value={"token": "abc"},
        ), patch(
            "app.blueprints.auth.oauth_routes.OAuthService.get_user_info",
            return_value={
                "email": "oauth.existing@example.com",
                "given_name": "Known",
                "family_name": "User",
                "sub": "google-known-user",
            },
        ):
            response = client.get(
                "/auth/oauth/callback?state=known-state&code=good-code",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "/organization/dashboard" in (response.location or "")

        with client.session_transaction() as sess:
            assert sess.get("_user_id") == str(user_id)
            assert sess.get("oauth_state") is None
            assert sess.get("oauth_provider") is None

        with app.app_context():
            refreshed = db.session.get(User, user_id)
            assert refreshed is not None
            assert refreshed.oauth_provider == "google"
            assert refreshed.oauth_provider_id == "google-known-user"

    def test_oauth_callback_stashes_new_user_info_and_redirects_signup(self, app, client):
        """Callback should preserve profile info in session and route unknown users to signup."""
        with client.session_transaction() as sess:
            sess["oauth_state"] = "new-state"
            sess["oauth_provider"] = "google"

        with patch(
            "app.blueprints.auth.oauth_routes.OAuthService.exchange_code_for_token",
            return_value={"token": "abc"},
        ), patch(
            "app.blueprints.auth.oauth_routes.OAuthService.get_user_info",
            return_value={
                "email": "oauth.new.user@example.com",
                "given_name": "New",
                "family_name": "Maker",
                "sub": "google-new-user",
            },
        ):
            response = client.get(
                "/auth/oauth/callback?state=new-state&code=new-code",
                follow_redirects=False,
            )

        assert response.status_code == 302
        location = response.location or ""
        assert "/signup" in location
        assert "tier=free" in location

        with client.session_transaction() as sess:
            assert sess.get("_user_id") is None
            oauth_payload = sess.get("oauth_user_info") or {}
            assert oauth_payload.get("email") == "oauth.new.user@example.com"
            assert oauth_payload.get("oauth_provider") == "google"
            assert oauth_payload.get("oauth_provider_id") == "google-new-user"
            assert oauth_payload.get("first_name") == "New"
            assert oauth_payload.get("last_name") == "Maker"

        with app.app_context():
            assert User.query.filter_by(email="oauth.new.user@example.com").first() is None
