import json
import os
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Optional

from lru_cache import LRUCache

import logging
import signal
import sys

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mini-redis")

CACHE_CAPACITY = int(os.environ.get("CACHE_CAPACITY", "5"))
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))
MAX_KEY_LENGTH = 256
MAX_VALUE_SIZE = 1024 * 1024  # 1MB

# Initialize our LRU Cache instance
cache = LRUCache(capacity=CACHE_CAPACITY)
server_start_time = time.time()

class CacheAPIHandler(BaseHTTPRequestHandler):
    """
    Zero-Dependency High-Performance HTTP Server & REST API.
    Handles static dashboard files + JSON API endpoints.
    """

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _log_request(self, start_time: float, status_code: int) -> None:
        latency_ms = (time.time() - start_time) * 1000
        logger.info("%s %s - %d - %.2fms", self.command, self.path, status_code, latency_ms)

    def log_message(self, format: str, *args: Any) -> None:
        """Override default logging to use structured logger."""
        logger.info("%s %s %s", self.client_address[0], self.command or "-", self.path or "-")

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        req_start = time.time()
        self._set_headers(200)
        self._log_request(req_start, 200)

    def do_GET(self) -> None:
        req_start = time.time()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. Serve Dashboard HTML
        if path in ["/", "/index.html"]:
            self._serve_file("static/index.html", "text/html")
            self._log_request(req_start, 200)
            return

        # 2. Serve Static Assets (CSS/JS)
        if path.startswith("/static/"):
            file_path = path.lstrip("/")
            content_type = "text/css" if path.endswith(".css") else "application/javascript"
            self._serve_file(file_path, content_type)
            self._log_request(req_start, 200)
            return

        # Health Check Endpoint
        if path == "/api/health":
            self._send_json(200, {
                "status": "healthy",
                "uptime_seconds": round(time.time() - server_start_time, 2),
                "cache_size": len(cache.cache) if hasattr(cache, "cache") else 0,
                "cache_capacity": getattr(cache, "capacity", CACHE_CAPACITY),
            })
            self._log_request(req_start, 200)
            return

        # 3. GET /api/stats
        if path == "/api/stats":
            stats = cache.get_stats()
            self._send_json(200, stats)
            self._log_request(req_start, 200)
            return

        # 4. GET /api/get?key=xyz
        if path == "/api/get":
            key = query_params.get("key", [None])[0]
            if not key:
                self._send_json(400, {"error": "Missing 'key' query parameter"})
                self._log_request(req_start, 400)
                return

            value = cache.get(key)
            if value is None:
                self._send_json(404, {"found": False, "key": key, "value": None, "message": "Key not found or expired"})
                self._log_request(req_start, 404)
            else:
                self._send_json(200, {"found": True, "key": key, "value": value})
                self._log_request(req_start, 200)
            return

        self._send_json(404, {"error": "Endpoint not found"})
        self._log_request(req_start, 404)

    def do_POST(self) -> None:
        req_start = time.time()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        body = self._read_json_body()

        if body is None:
            self._send_json(400, {"error": "Invalid JSON payload"})
            self._log_request(req_start, 400)
            return

        # 1. POST /api/set
        if path == "/api/set":
            if not body or "key" not in body or "value" not in body:
                self._send_json(400, {"error": "JSON body must contain 'key' and 'value'"})
                self._log_request(req_start, 400)
                return

            key = str(body["key"])
            if len(key) > MAX_KEY_LENGTH:
                self._send_json(400, {"error": f"Key exceeds maximum length of {MAX_KEY_LENGTH}"})
                self._log_request(req_start, 400)
                return

            value = body["value"]
            value_json = json.dumps(value)
            if len(value_json.encode('utf-8')) > MAX_VALUE_SIZE:
                self._send_json(400, {"error": f"Value exceeds maximum size of {MAX_VALUE_SIZE} bytes"})
                self._log_request(req_start, 400)
                return

            ttl = body.get("ttl_seconds")
            if ttl is not None:
                try:
                    ttl = float(ttl)
                except ValueError:
                    ttl = None

            res = cache.set(key, value, ttl_seconds=ttl)
            self._send_json(200, res)
            self._log_request(req_start, 200)
            return

        # 2. POST /api/benchmark (Stress-test simulator)
        if path == "/api/benchmark":
            num_ops = body.get("operations", 1000) if body else 1000
            bench_start_time = time.time()

            # Execute rapid operations
            for i in range(num_ops):
                cache.set(f"bench_{i % 10}", f"value_{i}")
                cache.get(f"bench_{(i * 3) % 10}")

            elapsed_sec = time.time() - bench_start_time
            if elapsed_sec > 0:
                ops_per_sec = round((num_ops * 2) / elapsed_sec, 2)
            else:
                ops_per_sec = 0.0
                
            avg_latency_ms = round((elapsed_sec / max((num_ops * 2), 1)) * 1000, 4)

            self._send_json(200, {
                "total_operations": num_ops * 2,
                "elapsed_seconds": round(elapsed_sec, 4),
                "throughput_ops_per_sec": ops_per_sec,
                "average_latency_ms": avg_latency_ms
            })
            self._log_request(req_start, 200)
            return

        self._send_json(404, {"error": "Endpoint not found"})
        self._log_request(req_start, 404)

    def do_DELETE(self) -> None:
        req_start = time.time()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/delete":
            key = query_params.get("key", [None])[0]
            if not key:
                self._send_json(400, {"error": "Missing 'key' query parameter"})
                self._log_request(req_start, 400)
                return

            deleted = cache.delete(key)
            self._send_json(200, {"success": deleted, "key": key})
            self._log_request(req_start, 200)
            return

        self._send_json(404, {"error": "Endpoint not found"})
        self._log_request(req_start, 404)

    # ==================== Helpers ====================

    def _serve_file(self, relative_path: str, content_type: str) -> None:
        full_path = os.path.join(os.path.dirname(__file__), relative_path)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        else:
            self._send_json(404, {"error": f"File {relative_path} not found"})

    def _read_json_body(self) -> Optional[dict]:
        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except ValueError:
            content_length = 0
            
        if content_length == 0:
            return {}
            
        raw_data = self.rfile.read(content_length)
        try:
            return json.loads(raw_data.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON body: %s", e)
            return None

    def _send_json(self, status_code: int, data: dict) -> None:
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps(data).encode("utf-8"))


def run_server(port: int = SERVER_PORT) -> None:
    server_address = ("", port)
    httpd = HTTPServer(server_address, CacheAPIHandler)
    
    def shutdown_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down...", signal.Signals(signum).name)
        if hasattr(cache, 'stop'):
            cache.stop()  # Stop the TTL sweeper thread
        httpd.server_close()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    
    logger.info("Mini-Redis Cache Service started on port %d", port)
    logger.info("Dashboard: http://localhost:%d", port)
    logger.info("Health check: http://localhost:%d/api/health", port)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server gracefully...")
        if hasattr(cache, 'stop'):
            cache.stop()
        httpd.server_close()

if __name__ == "__main__":
    run_server(SERVER_PORT)
