#!/usr/bin/env python3
"""Local dashboard for Pad8Booster.

Serves a single-page UI plus a JSON API. Runs against the real tablet when adb
can see one, and against the synthetic demo device otherwise (clearly labelled).

    python3 web/server.py            # demo data, http://0.0.0.0:8000
    python3 web/server.py --live     # use a connected device if present

Deliberately dependency-free: ``http.server`` from the standard library. No build
step, no npm install, nothing to keep patched.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from pad8booster import __version__  # noqa: E402
from pad8booster.bench import cold_start, compare_launches  # noqa: E402
from pad8booster.demo import demo_adb  # noqa: E402
from pad8booster.device import capabilities, probe, verify_pad8  # noqa: E402
from pad8booster.metrics import compare, take_snapshot  # noqa: E402
from pad8booster.packages import CATALOGUE, PROTECTED, plan, installed_packages  # noqa: E402
from pad8booster.profiles import PROFILES, Journal, apply_profile  # noqa: E402

LIVE = False


def build_payload() -> dict:
    """Assemble everything the dashboard renders."""
    demo = not LIVE
    try:
        if demo:
            before_adb, after_adb = demo_adb("before"), demo_adb("after")
        else:
            from pad8booster.adb import Adb

            serial = None
            adb = Adb(serial=serial)
            before_adb = after_adb = adb

        info = probe(before_adb)
        verdict = verify_pad8(info)
        caps = capabilities(before_adb)

        before = take_snapshot(before_adb, label="before")
        after = take_snapshot(after_adb, label="after" if demo else "now")

        journal = Journal.load(Path("/tmp/pad8booster-dashboard.json"))
        journal.entries = []
        profile = apply_profile(before_adb, "responsive", journal, dry_run=True)

        installed = installed_packages(before_adb)
        safe_plan = plan(installed, risks=["safe"])

        payload = {
            "mode": "demo" if demo else "live",
            "version": __version__,
            "device": info.to_dict(),
            "verification": verdict.to_dict(),
            "capabilities": caps,
            "snapshots": [before.to_dict(), after.to_dict()],
            "delta": compare(before, after),
            "profile": {
                "name": profile["profile"],
                "summary": profile["summary"],
                "caveat": profile["caveat"],
                "results": profile["results"],
            },
            "catalogue": {
                "entries": [r.to_dict() for r in CATALOGUE],
                "protected_count": len(PROTECTED),
                "safe_plan": [a.to_dict() for a in safe_plan],
            },
            "profiles": {
                name: {"summary": p.summary, "caveat": p.caveat}
                for name, p in PROFILES.items()
            },
        }

        if demo:
            payload["bench"] = [
                compare_launches(
                    cold_start(before_adb, "com.android.chrome", runs=5, settle_s=0),
                    cold_start(after_adb, "com.android.chrome", runs=5, settle_s=0),
                )
            ]
        else:
            payload["bench"] = []
        return payload
    except Exception as exc:  # pragma: no cover - defensive
        return {"mode": "error", "error": str(exc), "version": __version__}


class Handler(BaseHTTPRequestHandler):
    server_version = f"Pad8Booster/{__version__}"

    # Keep-alive needs a Content-Length on every response, which _send always
    # sets. HTTP/1.1 also stops proxies treating each asset as a new connection.
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, body: bytes, content_type: str, *, head: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # The dashboard is proxied through a preview host, so it must not try to
        # enforce an origin allowlist of its own.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _route(self, *, head: bool) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = (ROOT / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8", head=head)
        elif path == "/api/state":
            body = json.dumps(build_payload(), default=str).encode()
            self._send(200, body, "application/json", head=head)
        elif path == "/healthz":
            self._send(200, b'{"ok":true}', "application/json", head=head)
        elif path == "/favicon.ico":
            # Inline 1x1 transparent GIF; avoids a 404 in every proxy log.
            icon = bytes.fromhex("47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b")
            self._send(200, icon, "image/gif", head=head)
        else:
            self._send(404, b'{"error":"not found"}', "application/json", head=head)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._route(head=False)

    def do_HEAD(self) -> None:  # noqa: N802 - proxy/uptime health checks use HEAD
        self._route(head=True)

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("[dashboard] " + fmt % args + "\n")


def main() -> int:
    global LIVE
    parser = argparse.ArgumentParser(description="Pad8Booster dashboard")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--live", action="store_true", help="use a connected device")
    args = parser.parse_args()
    LIVE = args.live
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    mode = "live device" if LIVE else "synthetic demo data"
    print(f"Pad8Booster dashboard on http://{args.host}:{args.port} ({mode})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
