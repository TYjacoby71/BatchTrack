from datetime import datetime, timedelta, timezone

import pytest

from app.utils.cache_manager import app_cache


class _FakeRedis:
    def __init__(self, now_provider):
        self._now = now_provider
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, datetime] = {}

    def _purge_if_expired(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return
        if self._now() >= expires_at:
            self._values.pop(key, None)
            self._expires_at.pop(key, None)

    def set(self, key: str, value: str, ex: int | None = None):
        self._values[key] = str(value)
        if ex is None:
            self._expires_at.pop(key, None)
        else:
            self._expires_at[key] = self._now() + timedelta(seconds=int(ex))
        return True

    def exists(self, key: str) -> int:
        self._purge_if_expired(key)
        return 1 if key in self._values else 0

    def incr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = int(self._values.get(key, "0"))
        current += 1
        self._values[key] = str(current)
        return current

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self._purge_if_expired(key)
        if key not in self._values:
            return False
        self._expires_at[key] = self._now() + timedelta(seconds=int(ttl_seconds))
        return True

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            self._purge_if_expired(key)
            if key in self._values:
                self._values.pop(key, None)
                self._expires_at.pop(key, None)
                deleted += 1
        return deleted


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


def test_high_confidence_probe_blocks_immediately(app):
    client = app.test_client()

    first = client.get("/wp-admin/setup-config.php", follow_redirects=False)
    assert first.status_code == 403

    with app.app_context():
        from app.models.public_bot_trap import BotTrapIpState

        ip_state = BotTrapIpState.query.filter_by(ip="127.0.0.1").first()
        assert ip_state is not None
        assert ip_state.blocked_until is not None

    blocked_response = client.get("/tools/", follow_redirects=False)
    assert blocked_response.status_code == 403


def test_temporary_ip_block_expires_and_unblocks_public_routes(app, monkeypatch):
    client = app.test_client()
    from app.services.public_bot_trap_service import PublicBotTrapService

    app.config["BOT_TRAP_STRIKE_THRESHOLD"] = 2
    app.config["BOT_TRAP_STRIKE_WINDOW_SECONDS"] = 300
    app.config["BOT_TRAP_IP_BLOCK_SECONDS"] = 60
    app.config["BOT_TRAP_IP_BLOCK_MAX_SECONDS"] = 3600
    app.config["BOT_TRAP_PENALTY_RESET_SECONDS"] = 86400

    base_now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        PublicBotTrapService,
        "_utcnow",
        staticmethod(lambda: base_now),
    )

    first = client.get("/wp-admin/setup-config.php", follow_redirects=False)
    assert first.status_code == 403

    blocked_response = client.get("/tools/", follow_redirects=False)
    assert blocked_response.status_code == 403

    later = base_now + timedelta(seconds=90)
    monkeypatch.setattr(
        PublicBotTrapService,
        "_utcnow",
        staticmethod(lambda: later),
    )

    unblocked_response = client.get("/tools/", follow_redirects=False)
    assert unblocked_response.status_code == 200

    with app.app_context():
        from app.models.public_bot_trap import BotTrapIpState

        ip_state = BotTrapIpState.query.filter_by(ip="127.0.0.1").first()
        assert ip_state is None or ip_state.blocked_until is None


def test_redis_probe_hot_path_blocks_high_confidence_probe_immediately(
    app, monkeypatch
):
    client = app.test_client()
    from app.models.public_bot_trap import BotTrapIpState
    from app.services.public_bot_trap_service import PublicBotTrapService

    now_ref = {"value": datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)}
    fake_redis = _FakeRedis(lambda: now_ref["value"])
    monkeypatch.setattr(
        PublicBotTrapService,
        "_redis_client",
        classmethod(lambda cls: fake_redis),
    )
    monkeypatch.setattr(
        PublicBotTrapService,
        "_utcnow",
        staticmethod(lambda: now_ref["value"]),
    )

    app.config["BOT_TRAP_STRIKE_THRESHOLD"] = 3
    app.config["BOT_TRAP_STRIKE_WINDOW_SECONDS"] = 300
    app.config["BOT_TRAP_IP_BLOCK_SECONDS"] = 60
    app.config["BOT_TRAP_IP_BLOCK_MAX_SECONDS"] = 3600
    app.config["BOT_TRAP_PENALTY_RESET_SECONDS"] = 86400

    first = client.get("/wp-admin/setup-config.php", follow_redirects=False)
    assert first.status_code == 403

    with app.app_context():
        ip_state = BotTrapIpState.query.filter_by(ip="127.0.0.1").first()
        assert ip_state is not None
        assert ip_state.blocked_until is not None

    blocked_response = client.get("/tools/", follow_redirects=False)
    assert blocked_response.status_code == 403


def test_redis_temporary_block_ttl_unblocks_even_if_db_row_is_missing(app, monkeypatch):
    from app.extensions import db
    from app.models.public_bot_trap import BotTrapIpState
    from app.services.public_bot_trap_service import PublicBotTrapService

    now_ref = {"value": datetime(2026, 2, 21, 9, 0, tzinfo=timezone.utc)}
    fake_redis = _FakeRedis(lambda: now_ref["value"])
    monkeypatch.setattr(
        PublicBotTrapService,
        "_redis_client",
        classmethod(lambda cls: fake_redis),
    )
    monkeypatch.setattr(
        PublicBotTrapService,
        "_utcnow",
        staticmethod(lambda: now_ref["value"]),
    )

    with app.app_context():
        PublicBotTrapService.add_block(ip="198.51.100.25", ip_block_seconds=60)
        BotTrapIpState.query.filter_by(ip="198.51.100.25").delete()
        db.session.commit()

        assert PublicBotTrapService.is_blocked(ip="198.51.100.25") is True

        now_ref["value"] = now_ref["value"] + timedelta(seconds=90)
        assert PublicBotTrapService.is_blocked(ip="198.51.100.25") is False


def test_non_suspicious_unknown_path_does_not_auto_block(app):
    client = app.test_client()

    response = client.get("/totally-made-up-page", follow_redirects=False)
    assert response.status_code == 404

    with app.app_context():
        from app.models.public_bot_trap import BotTrapIpState

        assert BotTrapIpState.query.filter_by(ip="127.0.0.1").first() is None

    still_public = client.get("/tools/", follow_redirects=False)
    assert still_public.status_code == 200


def test_robots_txt_unknown_path_does_not_auto_block(app):
    client = app.test_client()

    response = client.get("/robots.txt", follow_redirects=False)
    assert response.status_code == 200

    with app.app_context():
        from app.models.public_bot_trap import BotTrapIpState

        assert BotTrapIpState.query.filter_by(ip="127.0.0.1").first() is None

    still_public = client.get("/tools/", follow_redirects=False)
    assert still_public.status_code == 200


def test_bot_trap_identity_blocks_are_db_backed(app):
    from app.services.public_bot_trap_service import PublicBotTrapService

    with app.app_context():
        PublicBotTrapService.add_block(email="spam@example.com", user_id=42)

        assert PublicBotTrapService.is_blocked(email="spam@example.com")
        assert PublicBotTrapService.is_blocked(user_id=42)

        from app.models.public_bot_trap import BotTrapIdentityBlock

        email_entry = BotTrapIdentityBlock.query.filter_by(
            block_type="email",
            value="spam@example.com",
        ).first()
        user_entry = BotTrapIdentityBlock.query.filter_by(
            block_type="user",
            value="42",
        ).first()
        assert email_entry is not None
        assert user_entry is not None


def test_bot_trap_hit_audit_logging_is_disabled_by_default(app):
    client = app.test_client()
    from app.services.public_bot_trap_service import PublicBotTrapService
    from app.models.public_bot_trap import BotTrapHit

    with app.app_context():
        app.config["BOT_TRAP_STRIKE_THRESHOLD"] = 999

    response = client.get("/wp-admin/setup-config.php", follow_redirects=False)
    assert response.status_code == 404

    with app.app_context():
        assert BotTrapHit.query.count() == 0
