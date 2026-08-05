# ⚡ Mini-Redis: FAANG-Tier In-Memory Cache Microservice

A high-performance, thread-safe **In-Memory Key-Value Storage & Cache Engine** built with $O(1)$ **Least Recently Used (LRU) Eviction**, **Time-To-Live (TTL) Auto-Expiry**, and a real-time **Telemetry & Live Queue Visualizer Dashboard**.

---

## 🌟 Key Features

* **$O(1)$ LRU Eviction Engine:** Combines a **HashMap** (instant lookups) with a **Doubly Linked List** (constant-time queue ordering).
* **Thread-Safe Concurrency:** Guarded with mutual exclusion locks (`threading.Lock`) to prevent race conditions during high-frequency concurrent operations.
* **Time-To-Live (TTL) Auto-Expiry:** Dedicated background sweeper thread purges expired keys safely without blocking client reads.
* **Zero Dependencies:** Pure Python 3 standard library backend (no heavy third-party framework overhead).
* **Live Telemetry & Dashboard:** Real-time web UI visualizer showing cache hit/miss rates, memory queue ordering, and interactive stress test benchmarks.

---

## ⚡ Algorithmic Complexity

| Operation | Time Complexity | Space Complexity | Description |
| :--- | :--- | :--- | :--- |
| `GET(key)` | **$O(1)$** | $O(1)$ | Instant lookup via HashMap + moves node to Head (MRU). |
| `SET(key, val)` | **$O(1)$** | $O(1)$ | Instant insert/update + evicts Tail (LRU) if capacity exceeded. |
| `DELETE(key)` | **$O(1)$** | $O(1)$ | Removes node from list and map in constant time. |

---

## 🚀 Quickstart Guide

### Option A: Direct Local Execution
```bash
python3 main.py
```
Open **`http://localhost:8000`** in your browser to launch the Live Visual Dashboard!

### Option B: Docker Container
```bash
docker build -t mini-redis .
docker run -p 8000:8000 mini-redis
```

---

## 🧪 Unit Tests & Benchmarking
Run the unit test suite:
```bash
python3 test_cache.py
```

---

## 🎯 How to Explain This Project in FAANG Interviews

> *"I engineered a thread-safe in-memory cache microservice capable of sub-millisecond response times. To prevent memory overflow, I implemented an $O(1)$ LRU eviction algorithm combining a Hash Map for constant-time key lookups and a Doubly Linked List for constant-time eviction ordering. The service includes background TTL expiration threads, concurrency mutex locks, and an interactive telemetry dashboard measuring throughput under high-frequency load tests."*
