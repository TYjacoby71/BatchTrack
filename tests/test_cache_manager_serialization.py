from __future__ import annotations

import pickle
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.utils import cache_manager

pytestmark = pytest.mark.skipif(
    cache_manager.redis is None, reason="redis package not available"
)


class _FakeRedisClient:
    def __init__(self):
        self.values: dict[str, bytes] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None):  # pragma: no cover
        self.values[key] = value
        return True

    def delete(self, *keys: str):  # pragma: no cover
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
                self.values.pop(key, None)
        return deleted


def test_redis_cache_json_serialization_round_trips(monkeypatch):
    cache = cache_manager.RedisCache(namespace="test-json", default_ttl=30)
    fake_client = _FakeRedisClient()
    monkeypatch.setattr(cache, "_get_client", lambda: fake_client)

    payload = {
        "name": "batchtrack",
        "count": 7,
        "active": True,
        "timestamp": datetime(2026, 2, 27, 12, 30, tzinfo=timezone.utc),
        "ship_date": date(2026, 3, 1),
        "amount": Decimal("19.95"),
        "labels": {"alpha", "beta"},
    }

    cache.set("roundtrip", payload)
    assert isinstance(fake_client.values[cache._k("roundtrip")], bytes)

    restored = cache.get("roundtrip")
    assert restored["name"] == "batchtrack"
    assert restored["count"] == 7
    assert restored["active"] is True
    assert restored["timestamp"] == payload["timestamp"]
    assert restored["ship_date"] == payload["ship_date"]
    assert restored["amount"] == payload["amount"]
    assert restored["labels"] == payload["labels"]


def test_redis_cache_drops_non_json_payload(monkeypatch):
    cache = cache_manager.RedisCache(namespace="test-json-invalid", default_ttl=30)
    fake_client = _FakeRedisClient()
    monkeypatch.setattr(cache, "_get_client", lambda: fake_client)

    redis_key = cache._k("legacy")
    fake_client.values[redis_key] = pickle.dumps({"legacy": "pickle"})

    assert cache.get("legacy") is None
    assert redis_key not in fake_client.values
