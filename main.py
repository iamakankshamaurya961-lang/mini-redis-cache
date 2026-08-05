import json
import os
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from lru_cache import LRUCache

# Initialize our LRU Cache instance (default capacity: 5 items for visual demonstration)
cache = LRUCache(capacity=5)

class CacheAPIHandler(BaseHTTPRequestHandler):
    """
    Zero-Dependency High-Performance HTTP Server & REST API.
    Handles static dashboard files + JSON API endpoints.
    """

    def _set_headers(self, status_code=200, content_type="application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self._set_headers(200)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. Serve Dashboard HTML
        if path in ["/", "/index.html"]:
            self._serve_file("static/index.html", "text/html")
            return

        # 2. Serve Static Assets (CSS/JS)
        if path.startswith("/static/"):
            file_path = path.lstrip("/")
            content_type = "text/css" if path.endswith(".css") else "application/javascript"
            self._serve_file(file_path, content_type)
            return

        # 3. GET /api/stats
        if path == "/api/stats":
            stats = cache.get_stats()
            self._send_json(200, stats)
            return

        # 4. GET /api/get?key=xyz
        if path == "/api/get":
            key = query_params.get("key", [None])[0]
            if not key:
                self._send_json(400, {"error": "Missing 'key' query parameter"})
                return

            value = cache.get(key)
            if value is None:
                self._send_json(44, {"found": False, "key": key, "value": None, "message": "Key not found or expired"})
            else:
                self._send_json(200, {"found": True, "key": key, "value": value})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        body = self._read_json_body()

        # 1. POST /api/set
        if path == "/api/set":
            if not body or "key" not in body or "value" not in body:
                self._send_json(400, {"error": "JSON body must contain 'key' and 'value'"})
                return

            key = str(body["key"])
            value = body["value"]
            ttl = body.get("ttl_seconds")
            if ttl is not None:
                try:
                    ttl = float(ttl)
                except ValueError:
                    ttl = None

            res = cache.set(key, value, ttl_seconds=ttl)
            self._send_json(200, res)
            return

        # 2. POST /api/benchmark (Stress-test simulator)
        if path == "/api/benchmark":
            num_ops = body.get("operations", 1000) if body else 1000
            start_time = time.time()

            # Execute rapid operations
            for i in range(num_ops):
                cache.set(f"bench_{i % 10}", f"value_{i}")
                cache.get(f"bench_{(i * 3) % 10}")

            elapsed_sec = time.time() - start_time
            ops_per_sec = round((num_ops * 2) / elapsed_sec, 2)
            avg_latency_ms = round((elapsed_sec / (num_ops * 2)) * 1000, 4)

            self._send_json(200, {
                "total_operations": num_ops * 2,
                "elapsed_seconds": round(elapsed_sec, 4),
                "throughput_ops_per_sec": ops_per_sec,
                "average_latency_ms": avg_latency_ms
            })
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/delete":
            key = query_params.get("key", [None])[0]
            if not key:
                self._send_json(400, {"error": "Missing 'key' query parameter"})
                return

            deleted = cache.delete(key)
            self._send_json(200, {"success": deleted, "key": key})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    # ==================== Helpers ====================

    def _serve_file(self, relative_path: str, content_type: str):
        full_path = os.path.join(os.path.dirname(__file__), relative_path)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        else:
            self._send_json(404, {"error": f"File {relative_path} not found"})

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw_data = self.rfile.read(content_length)
        try:
            return json.loads(raw_data.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, status_code: int, data: dict):
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps(data).encode("utf-8"))


def run_server(port: int = 8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, CacheAPIHandler)
    print(f"🚀 FAANG-Tier Cache Service running at http://localhost:{port}")
    print("📊 Dashboard available at http://localhost:8000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server gracefully...")
        httpd.server_close()

if __name__ == "__main__":
    run_server(8000)
