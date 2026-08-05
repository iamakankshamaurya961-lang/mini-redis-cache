import time
from lru_cache import LRUCache

def test_lru_cache():
    print("🧪 Running LRU Cache Unit Tests...\n")

    # 1. Test basic GET & SET
    cache = LRUCache(capacity=3)
    cache.set("a", "Apple")
    cache.set("b", "Banana")
    cache.set("c", "Cherry")

    assert cache.get("a") == "Apple", "Failed: Key 'a' should be Apple"
    assert cache.get("b") == "Banana", "Failed: Key 'b' should be Banana"
    print("✅ Test 1 Passed: Basic GET & SET working perfectly.")

    # 2. Test Eviction (Least Recently Used)
    # Since we just accessed 'a' and 'b', 'c' is now the Least Recently Used item!
    res = cache.set("d", "Dragonfruit")
    print(f"   Set 'd' -> Evicted Item: {res['evicted']}")

    assert res["evicted"]["key"] == "c", f"Failed: Expected 'c' to be evicted, got {res['evicted']}"
    assert cache.get("c") is None, "Failed: 'c' should no longer exist in cache"
    assert cache.get("d") == "Dragonfruit", "Failed: 'd' should be Dragonfruit"
    print("✅ Test 2 Passed: LRU Eviction successfully kicked out the oldest item.")

    # 3. Test TTL (Time-To-Live Expiration)
    cache.set("temp_key", "Flash Data", ttl_seconds=1.5)
    assert cache.get("temp_key") == "Flash Data", "Failed: Temp key should exist immediately"

    print("   Waiting 2 seconds for TTL expiration...")
    time.sleep(2.0)
    assert cache.get("temp_key") is None, "Failed: Temp key should have expired after 2 seconds"
    print("✅ Test 3 Passed: TTL Auto-Expiration working as expected.")

    # 4. Check Stats
    stats = cache.get_stats()
    print(f"\n📊 Final Cache Stats: Hits={stats['hits']}, Misses={stats['misses']}, Hit Rate={stats['hit_rate_pct']}%")
    print("🎉 All LRU Cache tests passed cleanly!\n")

if __name__ == "__main__":
    test_lru_cache()
