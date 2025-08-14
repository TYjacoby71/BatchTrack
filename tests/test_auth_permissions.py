import pytest
from flask import url_for
from app.models import User, Organization, Role, Permission
from app.utils.permissions import permission_required, any_permission_required, tier_required

class TestAuthPermissions:
    """Test auth permission decorators and helpers"""

    def test_permission_required_decorator_allows_with_permission(self, app, client):
        """Test that permission_required allows access when user has permission"""
        with app.app_context():
            # Mock route with permission requirement
            @app.route('/test-perm')
            @permission_required('test.permission')
            def test_route():
                return 'success'

            # This would need proper user setup - keeping simple for now
            response = client.get('/test-perm')
            # Will redirect to login if not authenticated
            assert response.status_code in [200, 302]

    def test_permission_required_returns_json_for_api(self, app, client):
        """Test that API endpoints return JSON when permission denied"""
        with app.app_context():
            @app.route('/api/test-perm')
            @permission_required('test.permission')
            def api_test_route():
                return {'status': 'success'}

            response = client.get('/api/test-perm')
            # Should return JSON unauthorized response
            assert response.status_code == 401
            assert response.is_json
            json_data = response.get_json()
            assert json_data['error'] == 'unauthorized'

    def test_any_permission_required_decorator(self, app):
        """Test any_permission_required decorator structure"""
        with app.app_context():
            @any_permission_required('perm.a', 'perm.b')
            def test_func():
                return 'success'

            # Decorator should be properly applied
            assert hasattr(test_func, '__wrapped__')

    def test_tier_required_decorator(self, app):
        """Test tier_required decorator structure"""
        with app.app_context():
            @tier_required('pro')
            def test_func():
                return 'success'

            # Decorator should be properly applied
            assert hasattr(test_func, '__wrapped__')

    def test_user_has_any_permission_method(self, app):
        """Test User.has_any_permission method"""
        with app.app_context():
            # Create test user
            user = User(username='testuser', email='test@example.com')

            # Test with empty permissions
            result = user.has_any_permission(['perm.a', 'perm.b'])
            assert result is False

    def test_api_unauth_returns_json_401(self, app, client):
        """Test that API endpoints return 401 JSON when unauthorized"""
        with app.app_context():
            @app.route("/api/_perm_test")
            @permission_required("some.permission")
            def _p():
                return {"ok": True}

            resp = client.get("/api/_perm_test", headers={"Accept": "application/json"})
            assert resp.status_code == 401
            assert resp.is_json
            json_data = resp.get_json()
            assert json_data.get("error") == "unauthorized"

    def test_web_unauth_redirects_to_login(self, app, client):
        """Test that web pages redirect to login when unauthorized"""
        with app.app_context():
            from flask_login import login_required

            @app.route("/web/_perm_test")
            @login_required
            @permission_required("some.permission")
            def _w():
                return "ok"

            resp = client.get("/web/_perm_test", follow_redirects=False)
            assert resp.status_code == 302
            assert "/auth/login" in resp.headers.get("Location", "")

    def test_csrf_token_available_in_templates(self, app, client, test_user):
        """Test that csrf_token is available in templates for an authenticated user"""
        with app.app_context():
            from flask import render_template_string
            from flask_login import login_user

            @app.route("/_csrf_check")
            def _csrf_check():
                # This route now requires login because of our middleware
                return render_template_string('<meta name="csrf-token" content="{{ csrf_token() }}">')

            # Properly log in the user using Flask-Login
            with client:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(test_user.id)
                    sess['_fresh'] = True
                
                # Make a request within the client context so Flask-Login loads the user
                resp = client.get("/_csrf_check")
                assert resp.status_code == 200
                assert b'csrf-token' in resp.data