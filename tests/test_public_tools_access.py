import json

import pytest


def _assert_public_get(client, path: str, *, label: str, **kwargs):
    """Helper to ensure a GET stays public and does not bounce to login."""
    response = client.get(path, follow_redirects=False, **kwargs)
    assert response.status_code == 200, f"{label} should be public (got {response.status_code})"
    location = response.headers.get("Location", "")
    assert "/auth/login" not in location, f"{label} unexpectedly redirected to login"
    return response


@pytest.mark.usefixtures("app")
def test_public_tools_pages_are_accessible(app):
    """Anonymous visitors should reach the tools landing and calculators without auth."""
    client = app.test_client()
    public_paths = [
        ("/tools/", "tools index"),
        ("/tools/soap", "soap calculator"),
        ("/tools/candles", "candle calculator"),
        ("/tools/lotions", "lotions calculator"),
        ("/tools/herbal", "herbal calculator"),
        ("/tools/baker", "baker calculator"),
    ]

    for path, label in public_paths:
        _assert_public_get(client, path, label=label)


@pytest.mark.usefixtures("app")
def test_public_soap_page_uses_marketing_header_without_center_overlay(app):
    """Anonymous soap page should use marketing nav without center-title overlay."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)

    assert 'id="publicMarketingNav"' in html
    assert '<span class="navbar-text fw-semibold">Soap Formulator</span>' not in html
    assert "position-absolute top-50 start-50 translate-middle text-center" not in html
    assert 'id="stageWaterOutput"' in html
    assert 'id="globalFeedbackNoteModal"' not in html


@pytest.mark.usefixtures("app")
def test_public_soap_calculation_api_is_accessible(app):
    """Anonymous users should be able to run soap calculations via tool API."""
    client = app.test_client()
    payload = {
        "oils": [{"grams": 650, "sap_koh": 190}],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 33},
    }
    response = client.post("/tools/api/soap/calculate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("success") is True
    result = data.get("result") or {}
    assert result.get("water_g", 0) > 0
    assert result.get("lye_adjusted_g", 0) > 0


@pytest.mark.usefixtures("app")
def test_public_soap_recipe_payload_api_is_accessible(app):
    """Anonymous users should be able to build soap draft payloads via tool API."""
    client = app.test_client()
    response = client.post(
        "/tools/api/soap/recipe-payload",
        json={
            "calc": {
                "totalOils": 650,
                "batchYield": 984,
                "lyeType": "NaOH",
                "superfat": 5,
                "purity": 100,
                "lyeAdjusted": 90,
                "water": 214,
                "waterMethod": "percent",
                "waterPct": 33,
                "lyeConcentration": 29.6,
                "waterRatio": 2.38,
                "oils": [
                    {
                        "name": "Olive Oil",
                        "grams": 650,
                    }
                ],
                "additives": {},
                "qualityReport": {},
            },
            "draft_lines": {"ingredients": [], "consumables": [], "containers": []},
            "context": {"unit_display": "g"},
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("success") is True
    result = data.get("result") or {}
    assert result.get("category_name") == "Soaps"
    assert result.get("predicted_yield_unit") == "gram"
    assert isinstance(result.get("notes"), str)


@pytest.mark.usefixtures("app")
def test_public_soap_quality_nudge_api_is_accessible(app):
    """Anonymous users should be able to request backend quality-target nudging."""
    client = app.test_client()
    response = client.post(
        "/tools/api/soap/quality-nudge",
        json={
            "oils": [
                {
                    "name": "Olive Oil",
                    "grams": 500,
                    "fatty_profile": {"oleic": 69, "linoleic": 12, "palmitic": 14, "stearic": 3},
                },
                {
                    "name": "Coconut Oil 76",
                    "grams": 150,
                    "fatty_profile": {"lauric": 48, "myristic": 19, "palmitic": 9, "stearic": 3, "oleic": 8},
                },
            ],
            "targets": {
                "hardness": 40,
                "cleansing": 15,
                "conditioning": 55,
                "bubbly": 25,
                "creamy": 25,
            },
            "target_oils_g": 650,
        },
    )
    assert response.status_code == 200
    data = response.get_json() or {}
    assert data.get("success") is True
    result = data.get("result") or {}
    assert result.get("ok") is True
    assert isinstance(result.get("adjusted_rows"), list)


@pytest.mark.usefixtures("app")
def test_public_soap_page_injects_backend_policy_config(app):
    """Soap tool page should inject backend-owned policy JSON for JS constants."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)
    assert "window.soapToolPolicy =" in html
    assert '"quality_ranges"' in html


@pytest.mark.usefixtures("app")
def test_public_feedback_note_api_saves_json_bucket_by_source_and_flow(app, monkeypatch, tmp_path):
    """Feedback notes should persist into source/flow JSON buckets."""
    from app.services.tools.feedback_note_service import ToolFeedbackNoteService

    monkeypatch.setattr(ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes")
    client = app.test_client()

    first_payload = {
        "source": "Soap Formulator",
        "flow": "glitch",
        "title": "Stage values jump",
        "message": "Oil percentages jump while typing in stage 2.",
        "context": "tools.soap",
        "page_endpoint": "batches.view_batch_in_progress",
        "page_path": "/batches/73/in-progress",
    }
    second_payload = {
        "source": "Soap Formulator",
        "flow": "question",
        "message": "What is the quality target range for cleansing?",
        "context": "tools.soap",
        "page_endpoint": "batches.view_batch_in_progress",
        "page_path": "/batches/73/in-progress",
    }
    third_payload = {
        "source": "Candles Tool",
        "flow": "missing_feature",
        "message": "Need wick calculator by vessel diameter.",
        "context": "tools.candles",
        "page_endpoint": "products.view_sku",
        "page_path": "/products/sku/44",
    }

    first_response = client.post("/tools/api/feedback-notes", json=first_payload)
    assert first_response.status_code == 200
    first_data = first_response.get_json() or {}
    assert first_data.get("success") is True
    assert (
        (first_data.get("result") or {}).get("bucket_path")
        == "batches_view_batch_in_progress/glitch.json"
    )

    second_response = client.post("/tools/api/feedback-notes", json=second_payload)
    assert second_response.status_code == 200
    third_response = client.post("/tools/api/feedback-notes", json=third_payload)
    assert third_response.status_code == 200

    batch_glitch_path = (
        tmp_path / "tool_feedback_notes" / "batches_view_batch_in_progress" / "glitch.json"
    )
    assert batch_glitch_path.exists()
    batch_glitch_bucket = json.loads(batch_glitch_path.read_text(encoding="utf-8"))
    assert batch_glitch_bucket.get("source") == "batches_view_batch_in_progress"
    assert batch_glitch_bucket.get("flow") == "glitch"
    assert batch_glitch_bucket.get("count") == 1
    assert (batch_glitch_bucket.get("entries") or [])[0].get("message") == first_payload["message"]

    batch_question_path = (
        tmp_path / "tool_feedback_notes" / "batches_view_batch_in_progress" / "question.json"
    )
    assert batch_question_path.exists()
    batch_question_bucket = json.loads(batch_question_path.read_text(encoding="utf-8"))
    assert batch_question_bucket.get("count") == 1

    global_index_path = tmp_path / "tool_feedback_notes" / "index.json"
    assert global_index_path.exists()
    global_index = json.loads(global_index_path.read_text(encoding="utf-8"))
    sources = global_index.get("sources") or []
    assert [source.get("source") for source in sources] == [
        "batches_view_batch_in_progress",
        "products_view_sku",
    ]

    batch_index = next(
        (source for source in sources if source.get("source") == "batches_view_batch_in_progress"),
        None,
    )
    assert batch_index is not None
    batch_flows = [flow.get("flow") for flow in (batch_index.get("flows") or [])]
    assert batch_flows == ["question", "glitch"]


@pytest.mark.usefixtures("app")
def test_customer_feedback_bubble_renders_when_flag_enabled_for_customer(app):
    """Authenticated customers should see the global feedback bubble when enabled."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag
    from app.models.models import User

    with app.app_context():
        flag = FeatureFlag.query.filter_by(key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE").first()
        if flag is None:
            flag = FeatureFlag(
                key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE",
                enabled=True,
                description="Customer feedback bubble",
            )
            db.session.add(flag)
        else:
            flag.enabled = True
        db.session.commit()
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        user_id = str(user.id)

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True

    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)
    assert 'id="globalFeedbackNoteModal"' in html
    assert 'data-lock-location-source="true"' in html
    assert 'id="globalFeedbackNoteModalSource"' not in html
    assert 'id="globalFeedbackNoteModalSourceLocked"' not in html
    assert "data-feedback-sort-summary" not in html
    assert "data-feedback-saved-path" not in html


@pytest.mark.usefixtures("app")
def test_public_feedback_bubble_renders_when_flag_enabled_for_anonymous(app):
    """Anonymous users should also see the bubble when the global flag is enabled."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    with app.app_context():
        flag = FeatureFlag.query.filter_by(key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE").first()
        if flag is None:
            flag = FeatureFlag(
                key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE",
                enabled=True,
                description="Customer feedback bubble",
            )
            db.session.add(flag)
        else:
            flag.enabled = True
        db.session.commit()

    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)
    assert 'id="globalFeedbackNoteModal"' in html
    assert 'data-lock-location-source="true"' in html
    assert 'id="globalFeedbackNoteModalSource"' not in html
    assert 'id="globalFeedbackNoteModalSourceLocked"' not in html
    assert "data-feedback-sort-summary" not in html
    assert "data-feedback-saved-path" not in html


@pytest.mark.usefixtures("app")
def test_public_feedback_note_api_rejects_unknown_flow(app, monkeypatch, tmp_path):
    """Unknown feedback flow values should fail validation."""
    from app.services.tools.feedback_note_service import ToolFeedbackNoteService

    monkeypatch.setattr(ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes")
    client = app.test_client()
    response = client.post(
        "/tools/api/feedback-notes",
        json={
            "source": "soap_formulator",
            "flow": "other",
            "message": "Something happened",
        },
    )
    assert response.status_code == 400
    data = response.get_json() or {}
    assert data.get("success") is False
    assert "allowed_flows" in data


@pytest.mark.usefixtures("app")
def test_public_feedback_note_api_honeypot_skips_note_write(app, monkeypatch, tmp_path):
    """Honeypot-triggered submissions should not write feedback note files."""
    from app.services.tools.feedback_note_service import ToolFeedbackNoteService
    from app.services.public_bot_trap_service import PublicBotTrapService

    monkeypatch.setattr(ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes")
    monkeypatch.setattr(PublicBotTrapService, "record_hit", lambda *args, **kwargs: None)
    monkeypatch.setattr(PublicBotTrapService, "add_block", lambda *args, **kwargs: None)
    monkeypatch.setattr(PublicBotTrapService, "block_email_if_user_exists", lambda *args, **kwargs: None)

    client = app.test_client()
    response = client.post(
        "/tools/api/feedback-notes",
        json={
            "source": "batches.view_batch_in_progress",
            "flow": "glitch",
            "message": "bot payload",
            "website": "spam.example",
            "page_endpoint": "batches.view_batch_in_progress",
            "page_path": "/batches/1/in-progress",
        },
    )
    assert response.status_code == 200
    data = response.get_json() or {}
    assert data.get("success") is True
    assert not (tmp_path / "tool_feedback_notes").exists()


@pytest.mark.usefixtures("app")
def test_anonymous_workflow_can_browse_public_site(app):
    """
    Simulate a public visitor navigating marketing pages so we detect regressions
    that accidentally require authentication (e.g., hitting authorize spots).
    """
    client = app.test_client()

    _assert_public_get(client, "/", label="homepage")
    _assert_public_get(client, "/tools/", label="tools landing")
    _assert_public_get(
        client,
        "/global-items",
        label="global items directory",
        query_string={"type": "ingredient"},
    )
    _assert_public_get(client, "/recipes/library", label="recipe library")
    _assert_public_get(client, "/help/how-it-works", label="how it works")
    _assert_public_get(client, "/lp/hormozi", label="landing page (results-first)")
    _assert_public_get(client, "/lp/robbins", label="landing page (transformation-first)")
    _assert_public_get(client, "/auth/signup", label="signup page")


@pytest.mark.usefixtures("app")
def test_public_branding_assets_are_accessible(app):
    """Logo and favicon assets should remain publicly available for marketing pages."""
    client = app.test_client()
    brand_asset_paths = [
        "/branding/full-logo.svg",
        "/branding/full-logo-header.svg",
        "/branding/app-tile.svg",
    ]

    for path in brand_asset_paths:
        response = _assert_public_get(client, path, label=f"branding asset {path}")
        assert response.mimetype == "image/svg+xml"
        body = response.get_data(as_text=True)
        assert "<svg" in body


@pytest.mark.usefixtures("app")
def test_public_crawler_assets_are_accessible(app):
    """Crawler assets should be available on root paths."""
    client = app.test_client()

    sitemap_response = _assert_public_get(client, "/sitemap.xml", label="sitemap.xml")
    sitemap_body = sitemap_response.get_data(as_text=True)
    assert sitemap_response.mimetype in {"application/xml", "text/xml"}
    assert "<urlset" in sitemap_body
    assert "https://www.batchtrack.com/" in sitemap_body

    robots_response = _assert_public_get(client, "/robots.txt", label="robots.txt")
    robots_body = robots_response.get_data(as_text=True)
    assert robots_response.mimetype == "text/plain"
    assert "User-agent:" in robots_body
    assert "Sitemap: https://www.batchtrack.com/sitemap.xml" in robots_body

    llms_response = _assert_public_get(client, "/llms.txt", label="llms.txt")
    llms_body = llms_response.get_data(as_text=True)
    assert llms_response.mimetype == "text/plain"
    assert "BatchTrack" in llms_body
    assert "Primary site: https://www.batchtrack.com/" in llms_body


@pytest.mark.usefixtures("app")
def test_legacy_dev_login_path_redirects_to_auth_namespace(app):
    """Legacy /dev-login URL should redirect to the canonical auth route."""
    client = app.test_client()
    response = client.get("/dev-login", follow_redirects=False)
    assert response.status_code in {301, 302}
    assert response.headers.get("Location", "").endswith("/auth/dev-login")


@pytest.mark.usefixtures("app")
def test_staging_homepage_variant_switcher_visibility(app):
    """Homepage variant switcher should only appear in staging."""
    client = app.test_client()

    app.config["ENV"] = "testing"
    app.config["FLASK_ENV"] = "testing"
    testing_response = _assert_public_get(
        client,
        "/",
        label="homepage in non-staging",
        query_string={"refresh": "1"},
    )
    testing_html = testing_response.get_data(as_text=True)
    assert "Home Variants" not in testing_html

    app.config["ENV"] = "staging"
    app.config["FLASK_ENV"] = "staging"
    staging_response = _assert_public_get(
        client,
        "/",
        label="homepage in staging",
        query_string={"refresh": "1"},
    )
    staging_html = staging_response.get_data(as_text=True)
    assert "Home Variants" in staging_html
    assert "/lp/hormozi" in staging_html
    assert "/lp/robbins" in staging_html
