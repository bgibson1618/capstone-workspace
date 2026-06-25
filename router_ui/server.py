"""ThreadingHTTPServer + request handler for the memory inspector.

Serves one static page (``static/index.html`` + ``app.js`` + ``styles.css``) and a small
read-only JSON API over a single, shared :class:`~router_ui.substrate.Substrate`
that is opened ONCE at startup (the stores are thread-safe, so requests share it). Binds
``127.0.0.1`` only. Stdlib only — no dependencies.

Routes
------
``GET  /``                         the inspector page
``GET  /app.js`` / ``/styles.css`` static assets (whitelisted; no path traversal)
``GET  /api/summary``              store path, profile, counts, fan-out histogram, flags
``GET  /api/memories``             the de-duped memory list (browse + routing)
``GET  /api/probe?q=...&k=5``      routing decision + per-backend + engine results
``GET  /api/backend-drill``        one Browse memory probed against one backend
``POST /api/capture``             append a captured eval case to captured_cases.jsonl
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# Whitelisted static assets -> (filename, content-type). No arbitrary path serving.
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class InspectorHandler(BaseHTTPRequestHandler):
    """Read-only inspector handler. ``substrate`` is bound per-server in :func:`build_server`."""

    substrate: Any = None        # the shared Substrate; set on the bound subclass
    server_version = "MemoryInspector/1.0"
    protocol_version = "HTTP/1.1"

    # -- GET ---------------------------------------------------------------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in _STATIC:
            return self._serve_static(path)
        if path == "/api/summary":
            return self._json(self.substrate.summary())
        if path == "/api/memories":
            return self._json({"memories": self.substrate.memories()})
        if path == "/api/probe":
            qs = parse_qs(parsed.query)
            query = (qs.get("q") or [""])[0]
            k = _int((qs.get("k") or ["5"])[0], default=5)
            return self._json(self.substrate.probe(query, k=k))
        if path == "/api/backend-drill":
            qs = parse_qs(parsed.query)
            item_id = (qs.get("item_id") or [""])[0]
            backend = (qs.get("backend") or [""])[0]
            k = _int((qs.get("k") or ["5"])[0], default=5)
            try:
                return self._json(self.substrate.probe_backend_for_memory(item_id, backend, k=k))
            except ValueError as exc:
                return self._json({"error": str(exc)}, code=400)
            except KeyError:
                return self._json({"error": f"memory not found: {item_id}"}, code=404)
        return self._json({"error": "not found", "path": path}, code=404)

    # -- POST --------------------------------------------------------------
    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/capture":
            return self._json({"error": "not found", "path": parsed.path}, code=404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as exc:
            return self._json({"error": f"bad request body: {exc}"}, code=400)
        try:
            result = self.substrate.capture(payload)
        except ValueError as exc:
            return self._json({"error": str(exc)}, code=400)
        return self._json(result)

    # -- helpers -----------------------------------------------------------
    def _serve_static(self, route: str) -> None:
        filename, ctype = _STATIC[route]
        try:
            data = (_STATIC_DIR / filename).read_bytes()
        except OSError:
            return self._json({"error": f"missing asset {filename}"}, code=500)
        self._raw(data, ctype)

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self._raw(body, "application/json; charset=utf-8", code=code)

    def _raw(self, data: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:  # client navigated away mid-response; not our problem
            pass

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches base signature
        """Quiet by default (one line per request to stderr would spam the terminal log)."""
        return


def _int(value: str, *, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def build_server(host: str, port: int, substrate) -> ThreadingHTTPServer:
    """A ThreadingHTTPServer bound to ``(host, port)`` serving ``substrate`` (shared across
    requests). The handler subclass carries the substrate so every thread reads the one
    opened-at-startup view."""
    handler = type("BoundInspectorHandler", (InspectorHandler,), {"substrate": substrate})
    return ThreadingHTTPServer((host, port), handler)


__all__ = ["build_server", "InspectorHandler"]
