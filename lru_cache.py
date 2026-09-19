import logging
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

class Node:
    """
    A single node in our Doubly Linked List.
    Holds the key, value, TTL expiration timestamp, and pointers to prev/next nodes.
    """
    def __init__(self, key: str, value: Any, ttl_seconds: float | None = None):
        if not isinstance(key, str) or not key or len(key) > 256:
            raise ValueError("Key must be a non-empty string up to 256 characters.")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("TTL must be a positive number")

        self.key = key
        self.value = value
        self.prev: Node | None = None
        self.next: Node | None = None
        # Calculate absolute expiration timestamp if TTL is provided
        self.expires_at: float | None = (time.time() + ttl_seconds) if ttl_seconds else None

    def is_expired(self) -> bool:
        """Returns True if the node has passed its TTL expiration timestamp."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class LRUCache:
    """
    FAANG-Tier In-Memory Cache Engine.
    Combines a HashMap (for O(1) lookups) with a Doubly Linked List (for O(1) eviction ordering).
    Includes thread-safety (Locking) and background TTL auto-expiry.
    """
    def __init__(self, capacity: int = 5, on_evict: Callable | None = None):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.capacity = capacity
        self.cache: dict[str, Node] = {}
        self.on_evict = on_evict

        # Dummy Sentinel Nodes (Head = Most Recently Used, Tail = Least Recently Used)
        # Using dummy nodes avoids edge-case checks for empty lists!
        # Bypass validation by creating an empty instance and mutating
        self.head = Node.__new__(Node)
        self.head.key = "HEAD_SENTINEL"
        self.head.value = None
        self.head.prev = None
        self.head.next = None
        self.head.expires_at = None

        self.tail = Node.__new__(Node)
        self.tail.key = "TAIL_SENTINEL"
        self.tail.value = None
        self.tail.prev = None
        self.tail.next = None
        self.tail.expires_at = None

        self.head.next = self.tail
        self.tail.prev = self.head

        # Concurrency Lock (prevents race conditions when multiple requests come in at once)
        self.lock = threading.Lock()

        # Performance Metrics
        self.hits = 0
        self.misses = 0
        self.total_reads = 0
        self.total_writes = 0

        # Background TTL Sweeper Thread
        self.running = True
        logger.info("TTL sweeper thread started")
        self.ttl_thread = threading.Thread(target=self._ttl_sweeper_loop, daemon=True)
        self.ttl_thread.start()

    def __len__(self) -> int:
        """Returns the number of items currently in the cache."""
        with self.lock:
            return len(self.cache)

    def __contains__(self, key: str) -> bool:
        """Supports 'in' operator. Does NOT count as a read or move items."""
        with self.lock:
            if key not in self.cache:
                return False
            return not self.cache[key].is_expired()

    # ==================== Doubly Linked List Helpers (O(1)) ====================

    def _add_node_to_front(self, node: Node) -> None:
        """Adds a node right after HEAD (marking it as Most Recently Used)."""
        node.prev = self.head
        node.next = self.head.next
        assert self.head.next is not None  # Sentinel node always has next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node: Node) -> None:
        """Removes an existing node from the Doubly Linked List in O(1) time."""
        prev_node = node.prev
        next_node = node.next
        if prev_node:
            prev_node.next = next_node
        if next_node:
            next_node.prev = prev_node

    def _move_to_front(self, node: Node) -> None:
        """Moves an existing node to the front (marking it as recently accessed)."""
        self._remove_node(node)
        self._add_node_to_front(node)

    def _pop_tail(self) -> Node | None:
        """Removes and returns the Least Recently Used node (the node right before TAIL)."""
        if self.tail.prev == self.head:
            return None
        lru_node = self.tail.prev
        assert lru_node is not None  # Guaranteed by sentinel check above
        self._remove_node(lru_node)
        return lru_node

    # ==================== Public API Methods ====================

    def get(self, key: str) -> Any | None:
        """
        Retrieves a value by key.
        Time Complexity: O(1)
        """
        with self.lock:
            self.total_reads += 1
            if key not in self.cache:
                self.misses += 1
                logger.debug("Cache GET: key=%s, hit=%s", key, False)
                return None

            node = self.cache[key]

            # Check if expired
            if node.is_expired():
                self.misses += 1
                self._remove_node(node)
                del self.cache[key]
                logger.debug("Cache GET: key=%s, hit=%s", key, False)
                return None

            # Hit! Move to front of LRU queue
            self.hits += 1
            self._move_to_front(node)
            logger.debug("Cache GET: key=%s, hit=%s", key, True)
            return node.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> dict[str, Any]:
        """
        Stores a key-value pair in cache with optional TTL.
        Evicts Least Recently Used item if capacity is exceeded.
        Time Complexity: O(1)
        """
        with self.lock:
            self.total_writes += 1
            evicted_item = None
            logger.debug("Cache SET: key=%s, ttl=%s", key, ttl_seconds)

            # If key already exists, update its value and move to front
            if key in self.cache:
                node = self.cache[key]
                node.value = value
                node.expires_at = (time.time() + ttl_seconds) if ttl_seconds else None
                self._move_to_front(node)
            else:
                # If cache is full, evict LRU node (item at back before tail)
                if len(self.cache) >= self.capacity:
                    lru_node = self._pop_tail()
                    if lru_node and lru_node.key in self.cache:
                        del self.cache[lru_node.key]
                        evicted_item = {"key": lru_node.key, "value": lru_node.value}
                        logger.info("LRU eviction: key=%s", lru_node.key)
                        if self.on_evict:
                            self.on_evict(lru_node.key, lru_node.value)

                # Create new node and add to front
                new_node = Node(key, value, ttl_seconds)
                self.cache[key] = new_node
                self._add_node_to_front(new_node)

            return {
                "success": True,
                "key": key,
                "value": value,
                "evicted": evicted_item
            }

    def delete(self, key: str) -> bool:
        """
        Deletes a key explicitly.
        Time Complexity: O(1)
        """
        with self.lock:
            found = key in self.cache
            logger.debug("Cache DELETE: key=%s, found=%s", key, found)
            if found:
                node = self.cache[key]
                self._remove_node(node)
                del self.cache[key]
                return True
            return False

    def get_stats(self) -> dict[str, Any]:
        """Returns real-time telemetry metrics."""
        with self.lock:
            total_ops = self.hits + self.misses
            hit_rate = (self.hits / total_ops * 100) if total_ops > 0 else 0.0

            # Gather ordered keys (from Most Recently Used -> Least Recently Used)
            items = []
            curr = self.head.next
            while curr and curr != self.tail:
                items.append({
                    "key": curr.key,
                    "value": curr.value,
                    "expires_in_sec": round(curr.expires_at - time.time(), 1) if curr.expires_at else None,
                    "is_expired": curr.is_expired()
                })
                curr = curr.next

            return {
                "capacity": self.capacity,
                "current_size": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_pct": round(hit_rate, 2),
                "total_reads": self.total_reads,
                "total_writes": self.total_writes,
                "items": items
            }

    def clear(self) -> None:
        """Removes all items from the cache and resets metrics."""
        with self.lock:
            self.cache.clear()
            self.head.next = self.tail
            self.tail.prev = self.head
            self.hits = 0
            self.misses = 0
            self.total_reads = 0
            self.total_writes = 0
            logger.info("Cache cleared")

    def keys(self) -> list[str]:
        """Returns a list of all non-expired keys in MRU order."""
        with self.lock:
            result = []
            curr = self.head.next
            while curr and curr != self.tail:
                if not curr.is_expired():
                    result.append(curr.key)
                curr = curr.next
            return result

    def stop(self) -> None:
        """Stops the TTL sweeper thread and performs graceful shutdown."""
        self.running = False
        if self.ttl_thread.is_alive():
            self.ttl_thread.join()
        logger.info("TTL sweeper thread stopped")

    # ==================== Background TTL Sweeper ====================

    def _ttl_sweeper_loop(self) -> None:
        """Background thread that periodically cleans up expired keys."""
        while self.running:
            time.sleep(1.0)  # Check every second
            with self.lock:
                expired_keys = [k for k, v in self.cache.items() if v.is_expired()]
                if expired_keys:
                    logger.info("TTL expired: %d keys swept", len(expired_keys))
                    for key in expired_keys:
                        node = self.cache[key]
                        self._remove_node(node)
                        del self.cache[key]
                        if self.on_evict:
                            self.on_evict(key, node.value)
