import json
import re

import pytest

_HEADING_LEVEL_PATTERN = re.compile(r"<h([1-6])\b", re.IGNORECASE)
_ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xdd\x8d\xb1\x00\x00\x00\x00IEND\xaeB`\x82"
)
_DUMMY_VIDEO_BYTES = b"batchtrack-demo-video-placeholder"
_SUPPORTED_MEDIA_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".avif",
    ".mp4",
    ".webm",
    ".ogg",
    ".mov",
    ".m4v",
}


def _first_nav_classes(html: str) -> str:
    match = re.search(r'<nav class="([^"]+)"', html)
    assert match is not None, "Expected a navbar element in response HTML"
    return match.group(1)


def _assert_public_get(client, path: str, *, label: str, **kwargs):
    """Helper to ensure a GET stays public and does not bounce to login."""
    response = client.get(path, follow_redirects=False, **kwargs)
    assert (
        response.status_code == 200
    ), f"{label} should be public (got {response.status_code})"
    location = response.headers.get("Location", "")
    assert "/auth/login" not in location, f"{label} unexpectedly redirected to login"
    return response


def _assert_no_heading_level_skips(html: str, *, label: str):
    """Ensure heading levels do not jump by more than one level."""
    levels = [int(match.group(1)) for match in _HEADING_LEVEL_PATTERN.finditer(html)]
    if not levels:
        return

    previous = levels[0]
    for current in levels[1:]:
        assert current <= previous + 1, (
            f"{label} has heading skip from h{previous} to h{current}"
        )
        previous = current


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
def test_tools_index_has_lang_and_ordered_category_headings(app):
    """Tools index should expose lang metadata and avoid heading-level skips."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/", label="tools index")
    html = response.get_data(as_text=True)

    assert "<html lang=\"en\"" in html
    assert '<h1 class="mb-1">Maker Tools</h1>' in html
    assert '<h2 class="card-title h5 mb-1">Soap Tools</h2>' in html
    assert '<h5 class="card-title mb-1">Soap Tools</h5>' not in html


@pytest.mark.usefixtures("app")
def test_public_soap_page_uses_centralized_guidance_dock(app):
    """Soap page should render the single centralized guidance dock surface."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)

    assert 'id="soapGuidanceDock"' in html
    assert 'id="soapGuidanceToggle"' in html
    assert 'id="soapGuidanceSummary"' in html
    assert 'id="soapGuidanceSections"' in html
    assert 'id="soapResultsActionsCard"' in html

    # Legacy scattered guidance surfaces should no longer be rendered.
    assert 'id="soapQualityWarnings"' not in html
    assert 'id="soapVisualGuidanceList"' not in html
    assert 'id="lyePurityHint"' not in html
    assert 'id="stageWaterComputedHint"' not in html
    assert 'id="oilLimitWarning"' not in html
    assert 'id="oilBlendTips"' not in html
    assert 'id="qualityHardnessHint"' not in html
    assert 'id="qualityCleansingHint"' not in html
    assert 'id="qualityConditioningHint"' not in html
    assert 'id="qualityBubblyHint"' not in html
    assert 'id="qualityCreamyHint"' not in html


@pytest.mark.usefixtures("app")
def test_public_soap_page_has_accessible_quality_controls(app):
    """Soap quality controls should expose explicit labels and named progressbars."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)

    assert '<label class="visually-hidden" for="qualityPreset">Quality preset</label>' in html
    assert '<label class="form-label" for="moldShape">Mold shape</label>' in html
    assert 'id="qualityHardnessBar" role="progressbar" aria-labelledby="qualityHardnessName"' in html
    assert 'id="qualityCleansingBar" role="progressbar" aria-labelledby="qualityCleansingName"' in html
    assert 'id="qualityConditioningBar" role="progressbar" aria-labelledby="qualityConditioningName"' in html
    assert 'id="qualityBubblyBar" role="progressbar" aria-labelledby="qualityBubblyName"' in html
    assert 'id="qualityCreamyBar" role="progressbar" aria-labelledby="qualityCreamyName"' in html
    assert 'id="iodineBar" role="progressbar" aria-labelledby="qualityIodineName"' in html
    assert 'id="insBar" role="progressbar" aria-labelledby="qualityInsName"' in html
    assert 'id="soapGuidanceOverlay"' in html
    assert 'aria-hidden="true"' in html
    assert 'inert' in html


@pytest.mark.usefixtures("app")
def test_public_soap_page_skips_heavy_analytics_payloads(app):
    """Soap page should not inject GA/PostHog providers into lightweight public shell."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)

    assert "www.googletagmanager.com/gtag/js" not in html
    assert "posthog.init(" not in html


@pytest.mark.usefixtures("app")
def test_public_marketing_pages_do_not_skip_heading_levels(app):
    """Public pages should keep heading levels sequential for accessibility."""
    client = app.test_client()
    public_pages = [
        ("/", "homepage"),
        ("/tools/", "tools index"),
        ("/tools/soap", "soap tool"),
        ("/tools/candles", "candles tool"),
        ("/tools/lotions", "lotions tool"),
        ("/tools/herbal", "herbal tool"),
        ("/tools/baker", "baker tool"),
        ("/pricing", "pricing"),
        ("/help/how-it-works", "how it works"),
        ("/help/system-faq", "system faq"),
        ("/legal/privacy", "privacy policy"),
        ("/legal/terms", "terms of service"),
        ("/legal/cookies", "cookie policy"),
        ("/lp/hormozi", "hormozi landing"),
        ("/lp/robbins", "robbins landing"),
    ]

    for path, label in public_pages:
        response = _assert_public_get(client, path, label=label)
        _assert_no_heading_level_skips(response.get_data(as_text=True), label=label)


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
                    "fatty_profile": {
                        "oleic": 69,
                        "linoleic": 12,
                        "palmitic": 14,
                        "stearic": 3,
                    },
                },
                {
                    "name": "Coconut Oil 76",
                    "grams": 150,
                    "fatty_profile": {
                        "lauric": 48,
                        "myristic": 19,
                        "palmitic": 9,
                        "stearic": 3,
                        "oleic": 8,
                    },
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
def test_public_feedback_note_api_saves_json_bucket_by_source_and_flow(
    app, monkeypatch, tmp_path
):
    """Feedback notes should persist into source/flow JSON buckets."""
    from app.services.tools.feedback_note_service import ToolFeedbackNoteService

    monkeypatch.setattr(
        ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes"
    )
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
    assert (first_data.get("result") or {}).get(
        "bucket_path"
    ) == "batches_view_batch_in_progress/glitch.json"

    second_response = client.post("/tools/api/feedback-notes", json=second_payload)
    assert second_response.status_code == 200
    third_response = client.post("/tools/api/feedback-notes", json=third_payload)
    assert third_response.status_code == 200

    batch_glitch_path = (
        tmp_path
        / "tool_feedback_notes"
        / "batches_view_batch_in_progress"
        / "glitch.json"
    )
    assert batch_glitch_path.exists()
    batch_glitch_bucket = json.loads(batch_glitch_path.read_text(encoding="utf-8"))
    assert batch_glitch_bucket.get("source") == "batches_view_batch_in_progress"
    assert batch_glitch_bucket.get("flow") == "glitch"
    assert batch_glitch_bucket.get("count") == 1
    assert (batch_glitch_bucket.get("entries") or [])[0].get(
        "message"
    ) == first_payload["message"]

    batch_question_path = (
        tmp_path
        / "tool_feedback_notes"
        / "batches_view_batch_in_progress"
        / "question.json"
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
        (
            source
            for source in sources
            if source.get("source") == "batches_view_batch_in_progress"
        ),
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
        flag = FeatureFlag.query.filter_by(
            key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE"
        ).first()
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
        flag = FeatureFlag.query.filter_by(
            key="FEATURE_CUSTOMER_FEEDBACK_BUBBLE"
        ).first()
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

    monkeypatch.setattr(
        ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes"
    )
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
    from app.services.public_bot_trap_service import PublicBotTrapService
    from app.services.tools.feedback_note_service import ToolFeedbackNoteService

    monkeypatch.setattr(
        ToolFeedbackNoteService, "BASE_DIR", tmp_path / "tool_feedback_notes"
    )
    monkeypatch.setattr(
        PublicBotTrapService, "record_hit", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(PublicBotTrapService, "add_block", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        PublicBotTrapService, "block_email_if_user_exists", lambda *args, **kwargs: None
    )

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
    _assert_public_get(
        client, "/lp/robbins", label="landing page (transformation-first)"
    )
    _assert_public_get(client, "/auth/signup", label="signup page")
    _assert_public_get(client, "/signup", label="signup short path")


@pytest.mark.usefixtures("app")
def test_signup_header_cta_uses_clean_short_path_by_default(app):
    """Signup header CTA should avoid default source query parameters."""
    client = app.test_client()
    response = _assert_public_get(client, "/auth/signup", label="signup page")
    html = response.get_data(as_text=True)

    assert 'href="/signup"' in html
    assert "/auth/signup?source=public_header" not in html


@pytest.mark.usefixtures("app")
def test_unauthenticated_public_pages_use_fixed_public_header_system(app):
    """Public pages should use the same fixed marketing header classes."""
    client = app.test_client()
    paths = [
        ("/", "homepage"),
        ("/tools/", "tools"),
        ("/pricing", "pricing"),
        ("/help/how-it-works", "help"),
        ("/auth/signup", "signup"),
    ]

    for path, label in paths:
        response = _assert_public_get(client, path, label=label)
        nav_classes = _first_nav_classes(response.get_data(as_text=True))
        assert "public-marketing-nav" in nav_classes
        assert "fixed-top" in nav_classes


@pytest.mark.usefixtures("app")
def test_authenticated_views_use_app_header_system(app):
    """Signed-in visitors should get the app-style navbar, not public shell nav."""
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        user_id = str(user.id)

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True

    response = client.get("/tools/", follow_redirects=False)
    assert response.status_code == 200
    nav_classes = _first_nav_classes(response.get_data(as_text=True))
    assert "public-marketing-nav" not in nav_classes
    assert "fixed-top" not in nav_classes


@pytest.mark.usefixtures("app")
def test_homepage_performance_and_accessibility_basics(app):
    """Homepage should keep key Lighthouse-focused optimizations in place."""
    client = app.test_client()
    response = _assert_public_get(
        client, "/", label="homepage", query_string={"refresh": "1"}
    )
    html = response.get_data(as_text=True)

    assert '<main id="main-content"' in html
    assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" not in html
    assert 'rel="preload"' in html
    assert "bootstrap.min.css" in html
    assert "this.onload=null;this.rel='stylesheet'" in html

    # All "Start Free Trial" links should resolve to the same destination.
    trial_links = re.findall(
        r'href="(/signup\?source=[^"]+)"[^>]*>\s*Start Free Trial\s*<',
        html,
    )
    assert len(trial_links) >= 3
    assert len(set(trial_links)) == 1


@pytest.mark.usefixtures("app")
def test_homepage_free_tools_cards_follow_feature_flag_toggles(app):
    """Homepage should show pinned soap plus enabled highest-priority tool cards."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    client = app.test_client()

    with app.app_context():
        desired_flags = {
            "TOOLS_SOAP": True,
            "TOOLS_LOTIONS": True,
            "TOOLS_BAKING": True,
            "TOOLS_CANDLES": False,
            "TOOLS_HERBAL": False,
        }
        for key, enabled in desired_flags.items():
            flag = FeatureFlag.query.filter_by(key=key).first()
            if flag is None:
                db.session.add(
                    FeatureFlag(
                        key=key,
                        enabled=enabled,
                        description=f"{key} test toggle",
                    )
                )
            else:
                flag.enabled = enabled
        db.session.commit()

    response = _assert_public_get(
        client, "/", label="homepage", query_string={"refresh": "1"}
    )
    html = response.get_data(as_text=True)

    assert "FREE TOOLS &amp; CALCULATORS" in html
    assert "Soap Maker Tool" in html
    assert "Lotion Maker Tool" in html
    assert "Baking Calculator" in html
    assert "Candle Maker Tool" not in html
    assert "Herbalist Calculator" not in html
    assert "Pinned" not in html
    assert 'href="/tools/soap"' in html
    assert 'href="/tools/lotions"' in html
    assert 'href="/tools/baker"' in html
    assert 'href="/tools/"' in html

    soap_idx = html.index("Soap Maker Tool")
    lotion_idx = html.index("Lotion Maker Tool")
    baking_idx = html.index("Baking Calculator")
    assert lotion_idx < soap_idx < baking_idx


@pytest.mark.usefixtures("app")
def test_homepage_tool_cards_render_uploaded_soap_image(app):
    """Homepage soap tool card should switch to uploaded card art when present."""
    from pathlib import Path

    client = app.test_client()

    with app.app_context():
        soap_image_path = (
            Path(app.static_folder) / "images/homepage/tools/soap/soap-tool-card.png"
        )
        soap_image_path.parent.mkdir(parents=True, exist_ok=True)
        created_for_test = False
        if not soap_image_path.exists():
            soap_image_path.write_bytes(_ONE_PIXEL_PNG)
            created_for_test = True

    try:
        response = _assert_public_get(
            client, "/", label="homepage", query_string={"refresh": "1"}
        )
        html = response.get_data(as_text=True)
        assert 'src="/static/images/homepage/tools/soap/soap-tool-card.png"' in html
    finally:
        if created_for_test:
            soap_image_path.unlink(missing_ok=True)


@pytest.mark.usefixtures("app")
def test_homepage_tool_cards_render_uploaded_soap_image_without_strict_filename(app):
    """Homepage soap card should render a custom upload filename from tool folder."""
    from pathlib import Path

    client = app.test_client()

    with app.app_context():
        soap_folder = Path(app.static_folder) / "images/homepage/tools/soap"
        soap_folder.mkdir(parents=True, exist_ok=True)
        canonical_name = soap_folder / "soap-tool-card.png"
        canonical_backup: Path | None = None
        if canonical_name.exists():
            canonical_backup = soap_folder / "soap-tool-card.png.bak-test"
            canonical_name.rename(canonical_backup)

        custom_name = soap_folder / "Screenshot 2026-02-23 173907.png"
        created_for_test = False
        if not custom_name.exists():
            custom_name.write_bytes(_ONE_PIXEL_PNG)
            created_for_test = True

    try:
        response = _assert_public_get(
            client, "/", label="homepage", query_string={"refresh": "1"}
        )
        html = response.get_data(as_text=True)
        assert (
            'src="/static/images/homepage/tools/soap/Screenshot%202026-02-23%20173707.png"'
            in html
        )
    finally:
        if created_for_test:
            custom_name.unlink(missing_ok=True)
        if canonical_backup is not None and canonical_backup.exists():
            canonical_backup.rename(canonical_name)


@pytest.mark.usefixtures("app")
def test_homepage_feature_cards_render_uploaded_image_without_strict_filename(app):
    """Homepage feature cards should render image from folder regardless of filename."""
    from pathlib import Path

    client = app.test_client()
    backups: list[tuple[Path, Path]] = []
    feature_folder: Path | None = None
    custom_name: Path | None = None

    with app.app_context():
        feature_folder = Path(app.static_folder) / "images/homepage/features/fifo-inventory"
        feature_folder.mkdir(parents=True, exist_ok=True)
        for candidate in feature_folder.iterdir():
            if (
                candidate.is_file()
                and not candidate.name.startswith(".")
                and candidate.suffix.lower()
                in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}
            ):
                backup = feature_folder / f"{candidate.name}.bak-test"
                candidate.rename(backup)
                backups.append((backup, candidate))

        custom_name = feature_folder / "000 Inventory Snapshot.png"
        custom_name.write_bytes(_ONE_PIXEL_PNG)

    try:
        response = _assert_public_get(
            client, "/", label="homepage", query_string={"refresh": "1"}
        )
        html = response.get_data(as_text=True)
        assert (
            'src="/static/images/homepage/features/fifo-inventory/000%20Inventory%20Snapshot.png"'
            in html
        )
    finally:
        if custom_name is not None and custom_name.exists():
            custom_name.unlink(missing_ok=True)
        for backup, original in backups:
            if backup.exists():
                backup.rename(original)


@pytest.mark.usefixtures("app")
def test_homepage_hero_slot_renders_uploaded_video_without_strict_filename(app):
    """Homepage hero slot should render media from folder with arbitrary filename."""
    from pathlib import Path

    client = app.test_client()
    backups: list[tuple[Path, Path]] = []
    hero_folder: Path | None = None
    custom_video: Path | None = None

    with app.app_context():
        hero_folder = Path(app.static_folder) / "images/homepage/hero/primary"
        hero_folder.mkdir(parents=True, exist_ok=True)
        for candidate in hero_folder.iterdir():
            if (
                candidate.is_file()
                and not candidate.name.startswith(".")
                and candidate.suffix.lower() in _SUPPORTED_MEDIA_EXTENSIONS
            ):
                backup = hero_folder / f"{candidate.name}.bak-test"
                candidate.rename(backup)
                backups.append((backup, candidate))

        custom_video = hero_folder / "000 hero clip.mp4"
        custom_video.write_bytes(_DUMMY_VIDEO_BYTES)

    try:
        response = _assert_public_get(
            client, "/", label="homepage", query_string={"refresh": "1"}
        )
        html = response.get_data(as_text=True)
        assert (
            'src="/static/images/homepage/hero/primary/000%20hero%20clip.mp4"' in html
        )
        assert 'class="hero-slot-media"' in html
    finally:
        if custom_video is not None and custom_video.exists():
            custom_video.unlink(missing_ok=True)
        for backup, original in backups:
            if backup.exists():
                backup.rename(original)


@pytest.mark.usefixtures("app")
def test_homepage_hero_slot_renders_uploaded_youtube_shortcut_without_hardcoded_id(app):
    """Homepage hero slot should render embed URL from youtube.url instead of fallback ID."""
    from pathlib import Path

    client = app.test_client()
    backups: list[tuple[Path, Path]] = []
    hero_folder: Path | None = None
    youtube_shortcut: Path | None = None

    with app.app_context():
        hero_folder = Path(app.static_folder) / "images/homepage/hero/primary"
        hero_folder.mkdir(parents=True, exist_ok=True)
        for candidate in hero_folder.iterdir():
            if (
                candidate.is_file()
                and not candidate.name.startswith(".")
                and candidate.suffix.lower() in (_SUPPORTED_MEDIA_EXTENSIONS | {".url"})
            ):
                backup = hero_folder / f"{candidate.name}.bak-test"
                candidate.rename(backup)
                backups.append((backup, candidate))

        youtube_shortcut = hero_folder / "youtube.url"
        youtube_shortcut.write_text(
            "[InternetShortcut]\nURL=https://youtu.be/dQw4w9WgXcQ\n",
            encoding="utf-8",
        )

    try:
        response = _assert_public_get(
            client, "/", label="homepage", query_string={"refresh": "1"}
        )
        html = response.get_data(as_text=True)
        assert (
            "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&amp;modestbranding=1&amp;playsinline=1"
            in html
        )
        assert 'class="hero-slot-media media-embed-frame"' in html
        assert "https://www.youtube.com/embed/NWTnxw_4GJw?rel=0" not in html
    finally:
        if youtube_shortcut is not None and youtube_shortcut.exists():
            youtube_shortcut.unlink(missing_ok=True)
        for backup, original in backups:
            if backup.exists():
                backup.rename(original)


@pytest.mark.usefixtures("app")
def test_help_gallery_renders_uploaded_media_without_strict_filename(app):
    """Help gallery should render media files from section folder by sorted order."""
    from pathlib import Path

    client = app.test_client()
    backups: list[tuple[Path, Path]] = []
    section_folder: Path | None = None
    custom_image: Path | None = None

    with app.app_context():
        section_folder = Path(app.static_folder) / "images/help/getting-started"
        section_folder.mkdir(parents=True, exist_ok=True)
        for candidate in section_folder.iterdir():
            if (
                candidate.is_file()
                and not candidate.name.startswith(".")
                and candidate.suffix.lower() in _SUPPORTED_MEDIA_EXTENSIONS
            ):
                backup = section_folder / f"{candidate.name}.bak-test"
                candidate.rename(backup)
                backups.append((backup, candidate))

        custom_image = section_folder / "A-first-help-shot.png"
        custom_image.write_bytes(_ONE_PIXEL_PNG)

    try:
        response = _assert_public_get(
            client, "/help/how-it-works", label="help overview"
        )
        html = response.get_data(as_text=True)
        assert 'src="/static/images/help/getting-started/A-first-help-shot.png"' in html
    finally:
        if custom_image is not None and custom_image.exists():
            custom_image.unlink(missing_ok=True)
        for backup, original in backups:
            if backup.exists():
                backup.rename(original)


@pytest.mark.usefixtures("app")
def test_homepage_tools_section_balances_desktop_cards_without_mobile_carousel_when_single_enabled(
    app,
):
    """Desktop should stay balanced while mobile avoids swipe controls for one enabled tool."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    client = app.test_client()

    with app.app_context():
        desired_flags = {
            "TOOLS_SOAP": True,
            "TOOLS_LOTIONS": False,
            "TOOLS_BAKING": False,
            "TOOLS_CANDLES": False,
            "TOOLS_HERBAL": False,
        }
        for key, enabled in desired_flags.items():
            flag = FeatureFlag.query.filter_by(key=key).first()
            if flag is None:
                db.session.add(
                    FeatureFlag(
                        key=key,
                        enabled=enabled,
                        description=f"{key} test toggle",
                    )
                )
            else:
                flag.enabled = enabled
        db.session.commit()

    response = _assert_public_get(
        client, "/", label="homepage", query_string={"refresh": "1"}
    )
    html = response.get_data(as_text=True)

    # Desktop cards stay visually balanced with two fallback cards.
    assert "Soap Maker Tool" in html
    assert "Lotion Maker Tool" in html
    assert "Baking Calculator" in html
    assert "Join Waitlist" in html
    assert "/waitlist?waitlist_key=tools.lotions" in html
    assert "/waitlist?waitlist_key=tools.baker" in html

    # Mobile should not render swipe carousel when only one tool is enabled.
    assert 'id="homepageToolsCarousel"' not in html


@pytest.mark.usefixtures("app")
def test_homepage_mobile_tool_carousel_shows_when_multiple_tools_enabled(app):
    """Mobile should render swipe carousel only when multiple enabled tools exist."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    client = app.test_client()

    with app.app_context():
        desired_flags = {
            "TOOLS_SOAP": True,
            "TOOLS_LOTIONS": True,
            "TOOLS_BAKING": False,
            "TOOLS_CANDLES": False,
            "TOOLS_HERBAL": False,
        }
        for key, enabled in desired_flags.items():
            flag = FeatureFlag.query.filter_by(key=key).first()
            if flag is None:
                db.session.add(
                    FeatureFlag(
                        key=key,
                        enabled=enabled,
                        description=f"{key} test toggle",
                    )
                )
            else:
                flag.enabled = enabled
        db.session.commit()

    response = _assert_public_get(
        client, "/", label="homepage", query_string={"refresh": "1"}
    )
    html = response.get_data(as_text=True)

    assert 'id="homepageToolsCarousel"' in html
    assert 'data-bs-wrap="true"' in html
    assert 'data-bs-touch="true"' in html


@pytest.mark.usefixtures("app")
def test_public_waitlist_page_is_accessible(app):
    """Anonymous visitors should be able to open the waitlist landing page."""
    client = app.test_client()
    response = _assert_public_get(
        client,
        "/waitlist",
        label="public waitlist",
        query_string={"waitlist_key": "tools.candles", "source": "homepage_tool_card"},
    )
    html = response.get_data(as_text=True)
    assert "Join the Candle Maker Tool waitlist" in html
    assert 'id="waitlistJoinForm"' in html


@pytest.mark.usefixtures("app")
def test_public_branding_assets_are_accessible(app):
    """Logo and favicon assets should remain publicly available for marketing pages."""
    client = app.test_client()
    brand_asset_paths = [
        "/favicon.ico",
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
def test_public_branding_assets_have_long_cache_lifetime(app):
    """Public brand SVGs should use long-lived immutable caching."""
    client = app.test_client()
    response = _assert_public_get(
        client, "/branding/full-logo-header.svg", label="branding header logo"
    )
    cache_control = response.headers.get("Cache-Control", "")
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


@pytest.mark.usefixtures("app")
def test_public_crawler_assets_are_accessible(app):
    """Crawler assets should be available on root paths."""
    client = app.test_client()

    sitemap_response = _assert_public_get(client, "/sitemap.xml", label="sitemap.xml")
    sitemap_body = sitemap_response.get_data(as_text=True)
    assert sitemap_response.mimetype in {"application/xml", "text/xml"}
    assert "<urlset" in sitemap_body
    assert "https://www.batchtrack.com/" in sitemap_body
    assert "https://www.batchtrack.com/signup" in sitemap_body
    assert "https://www.batchtrack.com/auth/signup" not in sitemap_body

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
def test_legacy_dev_login_path_is_not_exposed(app):
    """Legacy /dev-login URL should not expose an alternate auth path."""
    client = app.test_client()
    response = client.get("/dev-login", follow_redirects=False)
    assert response.status_code == 404


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
