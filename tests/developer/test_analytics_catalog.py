from app.services.statistics import AnalyticsCatalogService


def _login_as_developer(client, developer_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(developer_user.id)
        sess["_fresh"] = True


def test_catalog_service_domains_structure():
    domains = AnalyticsCatalogService.get_domains()
    assert isinstance(domains, list)
    assert domains, "Catalog should expose at least one domain"

    sample = domains[0]
    assert "key" in sample
    assert "storage" in sample and isinstance(sample["storage"], list)
    assert "metrics" in sample and sample["metrics"]

    # Ensure the unified analytics service is represented in at least one domain
    storage_models = {
        store["model"] for domain in domains for store in domain["storage"]
    }
    assert (
        "AnalyticsDataService" in storage_models
    ), "Catalog storage should reference AnalyticsDataService"


def test_developer_catalog_view_renders(client, developer_user):
    _login_as_developer(client, developer_user)

    resp = client.get("/developer/analytics-catalog")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Analytics Catalog" in body
    assert "Storage" in body
    assert "Metrics" in body
