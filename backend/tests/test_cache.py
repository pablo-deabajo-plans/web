from backend.app.core.cache import TTLCache


def test_ttl_cache_returns_cached_value_for_same_key() -> None:
    cache = TTLCache()
    calls = {"count": 0}

    def loader() -> int:
        calls["count"] += 1
        return 42

    first = cache.get_or_set("ns", "key", 30, loader)
    second = cache.get_or_set("ns", "key", 30, loader)

    assert first == 42
    assert second == 42
    assert calls["count"] == 1
