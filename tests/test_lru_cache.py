"""
Comprehensive pytest test suite for the LRU Cache Engine.
Covers: basic ops, eviction, TTL, concurrency, edge cases, new API methods.
"""
import time
import threading
import pytest
from lru_cache import LRUCache, Node


# =============================================================================
# Node Tests
# =============================================================================
class TestNode:
    """Tests for the Node class (input validation, expiration)."""

    def test_valid_node_creation(self) -> None:
        node = Node("key1", "value1")
        assert node.key == "key1"
        assert node.value == "value1"
        assert node.expires_at is None
        assert node.prev is None
        assert node.next is None

    def test_node_with_ttl(self) -> None:
        node = Node("key1", "value1", ttl_seconds=10.0)
        assert node.expires_at is not None
        assert not node.is_expired()

    def test_node_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            Node("", "value")

    def test_node_non_string_key_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            Node(123, "value")  # type: ignore[arg-type]

    def test_node_key_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="256 characters"):
            Node("x" * 257, "value")

    def test_node_max_length_key_ok(self) -> None:
        node = Node("x" * 256, "value")
        assert len(node.key) == 256

    def test_node_zero_ttl_raises(self) -> None:
        with pytest.raises(ValueError, match="positive number"):
            Node("key", "val", ttl_seconds=0)

    def test_node_negative_ttl_raises(self) -> None:
        with pytest.raises(ValueError, match="positive number"):
            Node("key", "val", ttl_seconds=-5)

    def test_node_expiration(self) -> None:
        node = Node("key", "val", ttl_seconds=0.1)
        assert not node.is_expired()
        time.sleep(0.15)
        assert node.is_expired()

    def test_node_no_ttl_never_expires(self) -> None:
        node = Node("key", "val")
        assert not node.is_expired()


# =============================================================================
# LRUCache — Basic GET/SET/DELETE
# =============================================================================
class TestCacheBasicOps:
    """Tests for basic cache operations: get, set, delete."""

    def test_set_and_get(self, cache: LRUCache) -> None:
        cache.set("a", "Apple")
        assert cache.get("a") == "Apple"

    def test_get_nonexistent_key(self, cache: LRUCache) -> None:
        assert cache.get("missing") is None

    def test_set_overwrites_existing(self, cache: LRUCache) -> None:
        cache.set("a", "Apple")
        cache.set("a", "Avocado")
        assert cache.get("a") == "Avocado"

    def test_delete_existing_key(self, cache: LRUCache) -> None:
        cache.set("a", "Apple")
        assert cache.delete("a") is True
        assert cache.get("a") is None

    def test_delete_nonexistent_key(self, cache: LRUCache) -> None:
        assert cache.delete("nope") is False

    def test_set_returns_success_dict(self, cache: LRUCache) -> None:
        result = cache.set("a", "Apple")
        assert result["success"] is True
        assert result["key"] == "a"
        assert result["value"] == "Apple"
        assert result["evicted"] is None

    def test_various_value_types(self, cache: LRUCache) -> None:
        """Cache should store any Python value type."""
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"nested": True})
        cache.set("bool", False)

        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"nested": True}
        assert cache.get("bool") is False


# =============================================================================
# LRUCache — Eviction
# =============================================================================
class TestCacheEviction:
    """Tests for LRU eviction behavior."""

    def test_evicts_least_recently_used(self, small_cache: LRUCache) -> None:
        small_cache.set("a", "1")
        small_cache.set("b", "2")
        small_cache.set("c", "3")
        # 'a' is LRU. Adding 'd' should evict 'a'
        result = small_cache.set("d", "4")
        assert result["evicted"]["key"] == "a"
        assert small_cache.get("a") is None
        assert small_cache.get("d") == "4"

    def test_get_updates_recency(self, small_cache: LRUCache) -> None:
        small_cache.set("a", "1")
        small_cache.set("b", "2")
        small_cache.set("c", "3")
        # Access 'a' to make it MRU — now 'b' is LRU
        small_cache.get("a")
        result = small_cache.set("d", "4")
        assert result["evicted"]["key"] == "b"

    def test_set_updates_recency(self, small_cache: LRUCache) -> None:
        small_cache.set("a", "1")
        small_cache.set("b", "2")
        small_cache.set("c", "3")
        # Re-set 'a' to make it MRU — now 'b' is LRU
        small_cache.set("a", "updated")
        result = small_cache.set("d", "4")
        assert result["evicted"]["key"] == "b"

    def test_single_capacity_eviction(self, single_cache: LRUCache) -> None:
        single_cache.set("a", "1")
        result = single_cache.set("b", "2")
        assert result["evicted"]["key"] == "a"
        assert single_cache.get("a") is None
        assert single_cache.get("b") == "2"

    def test_no_eviction_within_capacity(self, cache: LRUCache) -> None:
        for i in range(5):
            result = cache.set(f"key{i}", f"val{i}")
            assert result["evicted"] is None


# =============================================================================
# LRUCache — TTL Expiration
# =============================================================================
class TestCacheTTL:
    """Tests for Time-To-Live auto-expiration."""

    def test_key_expires_after_ttl(self, cache: LRUCache) -> None:
        cache.set("temp", "data", ttl_seconds=0.2)
        assert cache.get("temp") == "data"
        time.sleep(0.3)
        assert cache.get("temp") is None

    def test_key_accessible_before_ttl(self, cache: LRUCache) -> None:
        cache.set("temp", "data", ttl_seconds=5.0)
        assert cache.get("temp") == "data"

    def test_update_resets_ttl(self, cache: LRUCache) -> None:
        cache.set("temp", "v1", ttl_seconds=0.3)
        time.sleep(0.15)
        cache.set("temp", "v2", ttl_seconds=5.0)  # Reset TTL
        time.sleep(0.2)
        assert cache.get("temp") == "v2"  # Should still be alive

    def test_update_removes_ttl(self, cache: LRUCache) -> None:
        cache.set("temp", "v1", ttl_seconds=0.3)
        cache.set("temp", "v2")  # No TTL — should live forever
        time.sleep(0.4)
        assert cache.get("temp") == "v2"

    def test_expired_key_not_in_stats(self, cache: LRUCache) -> None:
        cache.set("temp", "data", ttl_seconds=0.2)
        time.sleep(0.3)
        # The sweeper or the get call should clean it
        cache.get("temp")  # trigger lazy cleanup
        stats = cache.get_stats()
        for item in stats["items"]:
            assert item["key"] != "temp"


# =============================================================================
# LRUCache — Stats & Metrics
# =============================================================================
class TestCacheStats:
    """Tests for the telemetry/stats API."""

    def test_initial_stats(self, cache: LRUCache) -> None:
        stats = cache.get_stats()
        assert stats["capacity"] == 5
        assert stats["current_size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_pct"] == 0.0
        assert stats["total_reads"] == 0
        assert stats["total_writes"] == 0

    def test_hit_miss_tracking(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total_reads"] == 2
        assert stats["total_writes"] == 1

    def test_hit_rate_calculation(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        cache.get("a")  # hit
        cache.get("a")  # hit
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.get_stats()
        assert stats["hit_rate_pct"] == 75.0

    def test_items_in_mru_order(self, small_cache: LRUCache) -> None:
        small_cache.set("a", "1")
        small_cache.set("b", "2")
        small_cache.set("c", "3")
        stats = small_cache.get_stats()
        keys = [item["key"] for item in stats["items"]]
        assert keys == ["c", "b", "a"]  # MRU to LRU


# =============================================================================
# LRUCache — New API Methods (clear, keys, len, contains, stop)
# =============================================================================
class TestCacheNewMethods:
    """Tests for newly added methods: clear, keys, __len__, __contains__, stop."""

    def test_clear_empties_cache(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_resets_metrics(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        cache.get("a")
        cache.get("missing")
        cache.clear()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_reads"] == 0
        assert stats["total_writes"] == 0

    def test_keys_returns_all_keys(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        keys = cache.keys()
        assert set(keys) == {"a", "b", "c"}

    def test_keys_in_mru_order(self, small_cache: LRUCache) -> None:
        small_cache.set("a", "1")
        small_cache.set("b", "2")
        small_cache.set("c", "3")
        assert small_cache.keys() == ["c", "b", "a"]

    def test_keys_excludes_expired(self, cache: LRUCache) -> None:
        cache.set("alive", "yes")
        cache.set("dying", "soon", ttl_seconds=0.1)
        time.sleep(0.15)
        keys = cache.keys()
        assert "alive" in keys
        assert "dying" not in keys

    def test_len(self, cache: LRUCache) -> None:
        assert len(cache) == 0
        cache.set("a", "1")
        assert len(cache) == 1
        cache.set("b", "2")
        assert len(cache) == 2
        cache.delete("a")
        assert len(cache) == 1

    def test_contains(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        assert "a" in cache
        assert "b" not in cache

    def test_contains_excludes_expired(self, cache: LRUCache) -> None:
        cache.set("temp", "val", ttl_seconds=0.1)
        assert "temp" in cache
        time.sleep(0.15)
        assert "temp" not in cache

    def test_contains_does_not_affect_metrics(self, cache: LRUCache) -> None:
        cache.set("a", "1")
        _ = "a" in cache
        _ = "b" in cache
        stats = cache.get_stats()
        assert stats["total_reads"] == 0  # __contains__ should NOT count as reads


# =============================================================================
# LRUCache — Eviction Callback
# =============================================================================
class TestEvictionCallback:
    """Tests for the on_evict callback feature."""

    def test_callback_on_eviction(self, cache_with_callback: LRUCache, eviction_log: list) -> None:
        cache_with_callback.set("a", "1")
        cache_with_callback.set("b", "2")
        cache_with_callback.set("c", "3")
        cache_with_callback.set("d", "4")  # Should evict 'a'
        assert len(eviction_log) == 1
        assert eviction_log[0]["key"] == "a"
        assert eviction_log[0]["value"] == "1"

    def test_no_callback_without_eviction(self, cache_with_callback: LRUCache, eviction_log: list) -> None:
        cache_with_callback.set("a", "1")
        cache_with_callback.set("b", "2")
        assert len(eviction_log) == 0

    def test_callback_on_ttl_expiry(self, eviction_log: list) -> None:
        def on_evict(key: str, value: object) -> None:
            eviction_log.append({"key": key, "value": value})

        c = LRUCache(capacity=5, on_evict=on_evict)
        c.set("temp", "flash", ttl_seconds=0.5)
        time.sleep(2.0)  # Wait for the sweeper to clean it
        c.stop()
        assert any(item["key"] == "temp" for item in eviction_log)


# =============================================================================
# LRUCache — Constructor Validation
# =============================================================================
class TestCacheValidation:
    """Tests for constructor parameter validation."""

    def test_zero_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            LRUCache(capacity=0)

    def test_negative_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            LRUCache(capacity=-3)

    def test_capacity_one_works(self) -> None:
        c = LRUCache(capacity=1)
        c.set("a", "1")
        assert c.get("a") == "1"
        c.stop()


# =============================================================================
# LRUCache — Thread Safety / Concurrency
# =============================================================================
class TestCacheConcurrency:
    """Tests for thread-safe concurrent access."""

    def test_concurrent_writes(self, cache: LRUCache) -> None:
        """Multiple threads writing should not corrupt state."""
        errors: list = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(100):
                    cache.set(f"t{thread_id}_k{i % 5}", f"v{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(cache) <= cache.capacity

    def test_concurrent_reads_and_writes(self, cache: LRUCache) -> None:
        """Mixed concurrent read/write should not raise or corrupt."""
        errors: list = []
        cache.set("shared", "initial")

        def reader() -> None:
            try:
                for _ in range(200):
                    cache.get("shared")
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for i in range(200):
                    cache.set("shared", f"v{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
