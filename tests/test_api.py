"""
API integration tests for the Mini-Redis Cache HTTP server.
Tests all REST endpoints, error handling, CORS, and validation.
"""
import json

# We need to import after setting up the cache, so we patch env vars
import os
import threading
import time
from http.server import HTTPServer

import pytest

os.environ["CACHE_CAPACITY"] = "5"
os.environ["SERVER_PORT"] = "9999"

from http.client import HTTPConnection

from main import CacheAPIHandler, cache


@pytest.fixture(scope="module")
def test_server():
    """Starts a test HTTP server on a separate thread for integration tests."""
    server = HTTPServer(("127.0.0.1", 9999), CacheAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)  # Give server time to start
    yield server
    server.shutdown()
    cache.stop()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clears the cache before each test to ensure isolation."""
    cache.clear()
    yield


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """Helper to make HTTP requests to the test server."""
    conn = HTTPConnection("127.0.0.1", 9999, timeout=5)
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    conn.request(method, path, body=data, headers=headers)
    response = conn.getresponse()
    status = response.status
    raw = response.read().decode("utf-8")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"raw": raw}
    conn.close()
    return status, result


# =============================================================================
# Health Check Endpoint
# =============================================================================
class TestHealthEndpoint:
    def test_health_returns_200(self, test_server: HTTPServer) -> None:
        status, data = _request("GET", "/api/health")
        assert status == 200
        assert data["status"] == "healthy"

    def test_health_has_uptime(self, test_server: HTTPServer) -> None:
        _status, data = _request("GET", "/api/health")
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_has_cache_info(self, test_server: HTTPServer) -> None:
        _status, data = _request("GET", "/api/health")
        assert "cache_size" in data
        assert "cache_capacity" in data


# =============================================================================
# SET Endpoint
# =============================================================================
class TestSetEndpoint:
    def test_set_key(self, test_server: HTTPServer) -> None:
        status, data = _request("POST", "/api/set", {"key": "foo", "value": "bar"})
        assert status == 200
        assert data["success"] is True
        assert data["key"] == "foo"
        assert data["value"] == "bar"

    def test_set_with_ttl(self, test_server: HTTPServer) -> None:
        status, data = _request("POST", "/api/set", {"key": "temp", "value": "data", "ttl_seconds": 60})
        assert status == 200
        assert data["success"] is True

    def test_set_missing_key(self, test_server: HTTPServer) -> None:
        status, data = _request("POST", "/api/set", {"value": "bar"})
        assert status == 400
        assert "error" in data

    def test_set_missing_value(self, test_server: HTTPServer) -> None:
        status, data = _request("POST", "/api/set", {"key": "foo"})
        assert status == 400
        assert "error" in data

    def test_set_empty_body(self, test_server: HTTPServer) -> None:
        status, _data = _request("POST", "/api/set", {})
        assert status == 400

    def test_set_key_too_long(self, test_server: HTTPServer) -> None:
        long_key = "x" * 300
        status, data = _request("POST", "/api/set", {"key": long_key, "value": "val"})
        assert status == 400
        assert "maximum length" in data["error"]

    def test_set_eviction_info(self, test_server: HTTPServer) -> None:
        # Fill cache to capacity (5)
        for i in range(5):
            _request("POST", "/api/set", {"key": f"k{i}", "value": f"v{i}"})
        # This should trigger eviction
        status, data = _request("POST", "/api/set", {"key": "overflow", "value": "extra"})
        assert status == 200
        assert data["evicted"] is not None
        assert "key" in data["evicted"]


# =============================================================================
# GET Endpoint
# =============================================================================
class TestGetEndpoint:
    def test_get_existing_key(self, test_server: HTTPServer) -> None:
        _request("POST", "/api/set", {"key": "hello", "value": "world"})
        status, data = _request("GET", "/api/get?key=hello")
        assert status == 200
        assert data["found"] is True
        assert data["value"] == "world"

    def test_get_missing_key(self, test_server: HTTPServer) -> None:
        status, data = _request("GET", "/api/get?key=nonexistent")
        assert status == 404
        assert data["found"] is False

    def test_get_no_key_param(self, test_server: HTTPServer) -> None:
        status, data = _request("GET", "/api/get")
        assert status == 400
        assert "error" in data

    def test_get_expired_key(self, test_server: HTTPServer) -> None:
        _request("POST", "/api/set", {"key": "expiring", "value": "soon", "ttl_seconds": 0.3})
        time.sleep(0.5)
        status, data = _request("GET", "/api/get?key=expiring")
        assert status == 404
        assert data["found"] is False


# =============================================================================
# DELETE Endpoint
# =============================================================================
class TestDeleteEndpoint:
    def test_delete_existing_key(self, test_server: HTTPServer) -> None:
        _request("POST", "/api/set", {"key": "del_me", "value": "bye"})
        status, data = _request("DELETE", "/api/delete?key=del_me")
        assert status == 200
        assert data["success"] is True

    def test_delete_nonexistent_key(self, test_server: HTTPServer) -> None:
        status, data = _request("DELETE", "/api/delete?key=nope")
        assert status == 200
        assert data["success"] is False

    def test_delete_no_key_param(self, test_server: HTTPServer) -> None:
        status, data = _request("DELETE", "/api/delete")
        assert status == 400
        assert "error" in data


# =============================================================================
# Stats Endpoint
# =============================================================================
class TestStatsEndpoint:
    def test_stats_structure(self, test_server: HTTPServer) -> None:
        status, data = _request("GET", "/api/stats")
        assert status == 200
        assert "capacity" in data
        assert "current_size" in data
        assert "hits" in data
        assert "misses" in data
        assert "hit_rate_pct" in data
        assert "items" in data

    def test_stats_reflect_operations(self, test_server: HTTPServer) -> None:
        _request("POST", "/api/set", {"key": "a", "value": "1"})
        _request("GET", "/api/get?key=a")     # hit
        _request("GET", "/api/get?key=miss")  # miss
        _status, data = _request("GET", "/api/stats")
        assert data["hits"] >= 1
        assert data["misses"] >= 1
        assert data["total_writes"] >= 1


# =============================================================================
# Benchmark Endpoint
# =============================================================================
class TestBenchmarkEndpoint:
    def test_benchmark_default(self, test_server: HTTPServer) -> None:
        status, data = _request("POST", "/api/benchmark", {"operations": 100})
        assert status == 200
        assert "total_operations" in data
        assert "throughput_ops_per_sec" in data
        assert "average_latency_ms" in data
        assert data["total_operations"] == 200  # 100 writes + 100 reads


# =============================================================================
# Error Handling & Edge Cases
# =============================================================================
class TestErrorHandling:
    def test_unknown_get_endpoint(self, test_server: HTTPServer) -> None:
        status, _data = _request("GET", "/api/unknown")
        assert status == 404

    def test_unknown_post_endpoint(self, test_server: HTTPServer) -> None:
        status, _data = _request("POST", "/api/unknown", {})
        assert status == 404

    def test_unknown_delete_endpoint(self, test_server: HTTPServer) -> None:
        status, _data = _request("DELETE", "/api/unknown")
        assert status == 404

    def test_cors_options(self, test_server: HTTPServer) -> None:
        conn = HTTPConnection("127.0.0.1", 9999, timeout=5)
        conn.request("OPTIONS", "/api/set")
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") == "*"
        conn.close()
