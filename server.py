#!/usr/bin/env python3
"""Local AI Rankings application, with an explicit source refresh operation."""
import argparse
import gzip
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import write_catalog
from refresh import refresh, ADAPTERS

state = {"running": False, "messages": [], "result": None}
lock = threading.Lock()
compressed_cache = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if args and str(args[1] if len(args) > 1 else "") not in ("200", "304"):
            super().log_message(fmt, *args)

    def send(self, data, content_type="application/json", status=200):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        compressed = len(data) > 4096 and "gzip" in self.headers.get("Accept-Encoding", "")
        if compressed:
            cache_key = (len(data), hash(data))
            if cache_key not in compressed_cache:
                if len(compressed_cache) > 10:
                    compressed_cache.clear()
                compressed_cache[cache_key] = gzip.compress(data, compresslevel=4)
            data = compressed_cache[cache_key]
        self.send_response(status)
        if compressed:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/refresh/status":
            return self.send(state)
        if path == "/api/data":
            file = ROOT / "data/catalog.json"
            if not file.exists():
                write_catalog()
            return self.send(file.read_bytes())
        if path == "/api/health":
            return self.send({"ok": True, "project": "ai-rankings"})
        if path == "/api/chart":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            provider = query.get("provider", [""])[0]
            try:
                if provider not in ADAPTERS:
                    raise ValueError("Unknown provider")
                i = int(query.get("index", ["-1"])[0])
                pack = json.loads((ROOT / "data/sources" / (provider + ".json")).read_text())
                if i < 0:
                    raise ValueError("Invalid chart")
                return self.send(pack.get("visualization_data", [])[i])
            except (ValueError, IndexError, OSError):
                return self.send({"error": "Chart not found"}, status=404)
        if path == "/icon.svg":
            return self.send((ROOT / "icon.svg").read_bytes(), "image/svg+xml")
        file = (ROOT / "app" / (path.lstrip("/") or "index.html")).resolve()
        if not file.is_relative_to(ROOT / "app") or any(part.startswith(".") for part in file.relative_to(ROOT / "app").parts) or not file.is_file():
            return self.send({"error": "Not found"}, status=404)
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self.send(file.read_bytes(), content_type)

    def do_POST(self):
        if self.path != "/api/refresh":
            return self.send({"error": "Not found"}, status=404)
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin not in allowed or self.headers.get("Content-Type") != "application/json":
            return self.send({"error": "Refresh requires a same-origin request"}, status=403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 4096:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            names = body.get("sources", list(ADAPTERS))
            if not isinstance(names, list) or any(n not in ADAPTERS for n in names):
                raise ValueError("Unknown source")
        except (ValueError, TypeError) as exc:
            return self.send({"error": str(exc)}, status=400)
        with lock:
            if state["running"]:
                return self.send(state, status=409)
            state.update(running=True, messages=[], result=None)
        def run():
            try:
                result = refresh(names, callback=lambda message: state["messages"].append(message), cache=False)
                state["result"] = result
            except Exception as exc:
                state["messages"].append(str(exc))
            finally:
                state["running"] = False
        threading.Thread(target=run, daemon=True).start()
        self.send(state, status=202)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    handler = Handler
    if not any((ROOT/'data/sources').glob('*.json')):
        from build_static import build
        build()
        class StaticHandler(SimpleHTTPRequestHandler):
            def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
            def do_GET(self):
                if self.path == '/api/health':
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(b'{"ok":true,"project":"ai-rankings"}')
                else:super().do_GET()
        handler=StaticHandler
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError:
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/health", timeout=2) as r:
                if json.load(r).get("project") != "ai-rankings":
                    raise RuntimeError("Port belongs to another application")
            if args.open:
                webbrowser.open(f"http://127.0.0.1:{args.port}")
            print(f"AI Rankings already running at http://127.0.0.1:{args.port}")
            sys.exit(0)
        except Exception:
            raise RuntimeError(f"Port {args.port} is in use. Choose another --port.")
    print(f"AI Rankings → http://127.0.0.1:{args.port}", flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
