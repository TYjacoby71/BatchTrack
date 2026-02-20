import re

from bs4 import BeautifulSoup


def test_pricing_page_uses_lightweight_shell_without_heavy_assets(app):
    client = app.test_client()
    response = client.get("/pricing")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "jquery-3.6.0.min.js" not in html
    assert "select2.min.js" not in html
    assert "js/core/SessionGuard.js" not in html
    assert "css/filter_panels" not in html
    assert "font-awesome/5.15.4/css/all.min.css" not in html
    assert "googletagmanager.com/gtag/js" not in html
    assert "posthog.init(" not in html
    assert "bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" in html


def test_pricing_checkout_labels_are_tier_specific(app):
    client = app.test_client()
    response = client.get("/pricing")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Checkout Monthly" not in html
    assert "Checkout Yearly" not in html

    soup = BeautifulSoup(html, "html.parser")
    checkout_links = [
        link.get_text(strip=True)
        for link in soup.find_all("a")
        if "Checkout" in link.get_text(strip=True)
    ]
    for label in checkout_links:
        assert re.match(r"Checkout\s+[A-Za-z0-9][A-Za-z0-9\s-]*\s+(Monthly|Yearly|Lifetime)$", label)


def test_pricing_comparison_section_rows_use_data_cells(app):
    client = app.test_client()
    response = client.get("/pricing")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    soup = BeautifulSoup(html, "html.parser")
    section_rows = soup.select("tr.comparison-section-row")
    assert section_rows, "Expected comparison section rows to be present."
    for row in section_rows:
        assert row.find("th") is None
        assert row.find("td") is not None
