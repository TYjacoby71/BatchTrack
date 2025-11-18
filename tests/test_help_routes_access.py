import pytest


@pytest.mark.usefixtures("app")
def test_help_pages_require_login(app):
    """Ensure help routes are gated behind authentication."""
    from app.models.models import User

    client = app.test_client()

    # Anonymous users should be redirected to the login page
    resp_overview = client.get("/help", follow_redirects=False)
    assert resp_overview.status_code in (301, 302)
    assert "/auth/login" in (resp_overview.headers.get("Location") or "")

    resp_faq = client.get("/help/system-faq", follow_redirects=False)
    assert resp_faq.status_code in (301, 302)
    assert "/auth/login" in (resp_faq.headers.get("Location") or "")

    # Log in using the seeded test user
    with app.app_context():
        user = User.query.first()

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True

    authed_overview = client.get("/help")
    assert authed_overview.status_code == 200
    assert b"How BatchTrack Works" in authed_overview.data

    authed_faq = client.get("/help/system-faq")
    assert authed_faq.status_code == 200
    assert b"Commonly Asked Questions" in authed_faq.data
