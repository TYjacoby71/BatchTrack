from bs4 import BeautifulSoup


def _links_with_exact_text(html: str, label: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    hrefs: list[str] = []
    for link in soup.find_all("a"):
        if link.get_text(strip=True) == label and link.get("href"):
            hrefs.append(link["href"])
    return hrefs


def test_help_start_free_trial_links_share_same_destination(app):
    client = app.test_client()
    response = client.get("/help")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    links = _links_with_exact_text(html, "Start Free Trial")
    assert len(links) >= 2
    assert len(set(links)) == 1
    assert "source=help_overview_start_free_trial" in links[0]


def test_landing_start_free_trial_links_share_same_destination(app):
    client = app.test_client()

    hormone_response = client.get("/lp/hormozi")
    assert hormone_response.status_code == 200
    hormone_links = _links_with_exact_text(
        hormone_response.get_data(as_text=True), "Start Free Trial"
    )
    assert len(hormone_links) >= 2
    assert len(set(hormone_links)) == 1
    assert "source=lp_hormozi_start_free_trial" in hormone_links[0]

    robbins_response = client.get("/lp/robbins")
    assert robbins_response.status_code == 200
    robbins_links = _links_with_exact_text(
        robbins_response.get_data(as_text=True), "Start Free Trial"
    )
    assert len(robbins_links) >= 2
    assert len(set(robbins_links)) == 1
    assert "source=lp_robbins_start_free_trial" in robbins_links[0]
