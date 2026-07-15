#!/usr/bin/env python3
"""Serve ``web/`` and proxy ``/api/*`` to the KOI FastAPI server."""

from __future__ import annotations

import argparse
import http.client
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

WEB_ROOT = os.path.join(os.path.dirname(__file__), "..", "web")
API_PREFIX = "/api"


class KoiWebHandler(SimpleHTTPRequestHandler):
    api_host = "127.0.0.1"
    api_port = 8010

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(WEB_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _proxy_api(self) -> None:
        path = self.path
        if path.startswith(API_PREFIX):
            path = path[len(API_PREFIX) :] or "/"
        url = urlparse(path)
        upstream_path = url.path
        if url.query:
            upstream_path = f"{upstream_path}?{url.query}"

        content_length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(content_length) if content_length else None

        headers = {}
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in {"host", "connection", "content-length"}:
                continue
            headers[key] = value

        conn = http.client.HTTPConnection(self.api_host, self.api_port, timeout=120)
        try:
            conn.request(self.command, upstream_path, body=body, headers=headers)
            resp = conn.getresponse()
            payload = resp.read()
            self.send_response(resp.status)
            for key, value in resp.getheaders():
                lower = key.lower()
                if lower in {"transfer-encoding", "connection"}:
                    continue
                self.send_header(key, value)
            self.end_headers()
            if payload:
                self.wfile.write(payload)
        except OSError as exc:
            msg = f'{{"detail":"API unavailable on {self.api_host}:{self.api_port}: {exc}"}}'
            body_bytes = msg.encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        finally:
            conn.close()

    def do_GET(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        super().do_HEAD()

    def do_OPTIONS(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization",
            )
            self.end_headers()
            return
        super().do_OPTIONS()

    def do_POST(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        self.send_error(405)

    def do_PUT(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        self.send_error(405)

    def do_PATCH(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        self.send_error(405)

    def do_DELETE(self) -> None:
        if self.path == API_PREFIX or self.path.startswith(f"{API_PREFIX}/"):
            self._proxy_api()
            return
        self.send_error(405)


def main() -> None:
    parser = argparse.ArgumentParser(description="KOI web static server + /api proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8010)
    args = parser.parse_args()

    KoiWebHandler.api_host = args.api_host
    KoiWebHandler.api_port = args.api_port

    server = ThreadingHTTPServer((args.host, args.port), KoiWebHandler)
    sys.stderr.write(
        f"KOI web on http://{args.host}:{args.port}/ (API proxy → {args.api_host}:{args.api_port})\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
