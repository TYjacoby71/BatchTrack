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
