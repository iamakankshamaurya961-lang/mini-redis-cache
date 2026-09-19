"""
Shared pytest fixtures for Mini-Redis Cache test suite.
"""
import pytest

from lru_cache import LRUCache


@pytest.fixture
def cache() -> LRUCache:
    """Provides a fresh LRUCache instance with capacity=5 for each test."""
    c = LRUCache(capacity=5)
    yield c
    c.stop()


@pytest.fixture
def small_cache() -> LRUCache:
    """Provides a small LRUCache with capacity=3 for eviction tests."""
    c = LRUCache(capacity=3)
    yield c
    c.stop()


@pytest.fixture
def single_cache() -> LRUCache:
    """Provides a minimal LRUCache with capacity=1 for edge-case tests."""
    c = LRUCache(capacity=1)
    yield c
    c.stop()


@pytest.fixture
def eviction_log() -> list:
    """Provides a mutable list to capture eviction callbacks."""
    return []


@pytest.fixture
def cache_with_callback(eviction_log: list) -> LRUCache:
    """Provides a cache with an eviction callback that logs evicted items."""
    def on_evict(key: str, value: object) -> None:
        eviction_log.append({"key": key, "value": value})

    c = LRUCache(capacity=3, on_evict=on_evict)
    yield c
    c.stop()
