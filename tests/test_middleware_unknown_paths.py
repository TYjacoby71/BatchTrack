import pytest

from app.utils.cache_manager import app_cache
from app.utils.json_store import read_json_file


@pytest.fixture(autouse=True)
def _isolated_bot_trap_state(tmp_path):
    from app.services.public_bot_trap_service import PublicBotTrapService

    original_path = PublicBotTrapService.BOT_TRAP_FILE
    PublicBotTrapService.BOT_TRAP_FILE = str(tmp_path / "bot_traps.json")
    try:
        yield
    finally:
        PublicBotTrapService.BOT_TRAP_FILE = original_path


def test_unknown_unauthenticated_path_returns_404(app):
    client = app.test_client()

    response = client.get("/ssl.key", follow_redirects=False)

    assert response.status_code == 404
    assert "/auth/login" not in (response.headers.get("Location") or "")
    assert response.get_data(as_text=True) == "Not Found"


def test_unknown_api_path_returns_json_404(app):
    client = app.test_client()

    response = client.get(
        "/api/not-a-real-endpoint",
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Not found"


def test_known_protected_route_still_redirects_to_login(app):
    client = app.test_client()

    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code in {302, 303}
    location = response.headers.get("Location") or ""
    assert "/auth/login" in location
    assert "next=" in location


def test_health_endpoint_is_public_without_auth(app):
    client = app.test_client()

    response = client.get("/health", follow_redirects=False)

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}
    assert "/auth/login" not in (response.headers.get("Location") or "")


def test_ping_and_head_health_probes_return_success(app):
    client = app.test_client()

    ping_response = client.get("/ping", follow_redirects=False)
    health_head = client.head("/health", follow_redirects=False)
    ping_head = client.head("/ping", follow_redirects=False)

    assert ping_response.status_code == 200
    assert ping_response.is_json
    assert ping_response.get_json() == {"status": "ok"}
    assert health_head.status_code == 200
    assert ping_head.status_code == 200


def test_marketing_context_skips_expensive_work_for_login(app, monkeypatch):
    client = app.test_client()
    from app import template_context

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("read_json_file should not be called for /auth/login")

    monkeypatch.setattr(template_context, "read_json_file", _fail_if_called)

    response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 200


def test_marketing_context_still_runs_for_homepage(app, monkeypatch):
    client = app.test_client()
    from app import template_context

    calls = []

    def _record_calls(_path, default=None):
        calls.append(str(_path))
        return default if default is not None else []

    monkeypatch.setattr(template_context, "read_json_file", _record_calls)
    app_cache.clear_prefix("marketing:")

    response = client.get("/", query_string={"refresh": "1"}, follow_redirects=False)

    assert response.status_code == 200
    assert calls


def test_suspicious_unknown_probe_auto_blocks_request_ip(app):
    client = app.test_client()
    from app.services.public_bot_trap_service import PublicBotTrapService

    response = client.get("/wp-admin/setup-config.php", follow_redirects=False)
    assert response.status_code == 404

    state = read_json_file(PublicBotTrapService.BOT_TRAP_FILE, default={}) or {}
    assert "127.0.0.1" in (state.get("blocked_ips") or [])

    blocked_response = client.get("/tools/", follow_redirects=False)
    assert blocked_response.status_code == 403


def test_non_suspicious_unknown_path_does_not_auto_block(app):
    client = app.test_client()
    from app.services.public_bot_trap_service import PublicBotTrapService

    response = client.get("/totally-made-up-page", follow_redirects=False)
    assert response.status_code == 404

    state = read_json_file(PublicBotTrapService.BOT_TRAP_FILE, default={}) or {}
    assert "127.0.0.1" not in (state.get("blocked_ips") or [])

    still_public = client.get("/tools/", follow_redirects=False)
    assert still_public.status_code == 200


def test_robots_txt_unknown_path_does_not_auto_block(app):
    client = app.test_client()
    from app.services.public_bot_trap_service import PublicBotTrapService

    response = client.get("/robots.txt", follow_redirects=False)
    assert response.status_code == 200

    state = read_json_file(PublicBotTrapService.BOT_TRAP_FILE, default={}) or {}
    assert "127.0.0.1" not in (state.get("blocked_ips") or [])

    still_public = client.get("/tools/", follow_redirects=False)
    assert still_public.status_code == 200
