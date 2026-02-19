import pytest


@pytest.mark.usefixtures("app")
def test_help_pages_are_public(app):
    """Unauthenticated visitors should have full access to help content."""
    client = app.test_client()

    resp_overview = client.get("/help")
    assert resp_overview.status_code == 200
    assert b"How BatchTrack Works" in resp_overview.data

    resp_faq = client.get("/help/system-faq")
    assert resp_faq.status_code == 200
    assert b"Commonly Asked Questions" in resp_faq.data


@pytest.mark.usefixtures("app")
def test_help_pages_use_lightweight_public_shell(app):
    """Public help pages should avoid loading heavy app-shell assets."""
    client = app.test_client()
    response = client.get("/help")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "jquery-3.6.0.min.js" not in html
    assert "select2.min.js" not in html
    assert "js/core/SessionGuard.js" not in html
    assert "css/filter_panels" not in html
    assert "font-awesome/5.15.4/css/all.min.css" not in html
    assert "bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" in html


@pytest.mark.usefixtures("app")
def test_legal_pages_use_lightweight_public_shell(app):
    """Legal pages should share the lightweight public shell strategy."""
    client = app.test_client()
    response = client.get("/legal/privacy")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "jquery-3.6.0.min.js" not in html
    assert "js/core/SessionGuard.js" not in html
    assert "css/filter_panels" not in html
