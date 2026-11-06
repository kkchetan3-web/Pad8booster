"""Integration tests for the dashboard server.

These bind a real socket on an ephemeral port, so they verify the HTTP layer
(including HEAD support, which proxies and uptime checkers rely on) rather than
just the payload builder.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import pytest

from web.server import DashboardServer, Handler


@pytest.fixture(scope="module")
def base_url():
    server = DashboardServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.headers, resp.read()


def test_index_serves_html(base_url):
    status, headers, body = _get(base_url + "/")
    assert status == 200
    assert "text/html" in headers["Content-Type"]
    assert b"PAD8BOOSTER" in body or b"Pad8Booster" in body


def test_head_is_supported_by_index(base_url):
    status, headers, body = _get(base_url + "/", method="HEAD")
    assert status == 200
    assert body == b""
    assert int(headers["Content-Length"]) > 0


def test_api_state_is_valid_json(base_url):
    status, headers, body = _get(base_url + "/api/state")
    assert status == 200
    assert "application/json" in headers["Content-Type"]
    data = json.loads(body)
    for key in ("mode", "device", "verification", "delta", "catalogue"):
        assert key in data
    assert data["mode"] in {"demo", "live", "error"}


def test_api_state_head_has_no_body(base_url):
    status, _, body = _get(base_url + "/api/state", method="HEAD")
    assert status == 200
    assert body == b""


def test_healthz(base_url):
    status, _, body = _get(base_url + "/healthz")
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_favicon_does_not_404(base_url):
    status, _, _ = _get(base_url + "/favicon.ico")
    assert status == 200


def test_unknown_path_is_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base_url + "/nope")
    assert exc.value.code == 404


def test_cors_header_allows_preview_proxy(base_url):
    _, headers, _ = _get(base_url + "/api/state")
    assert headers["Access-Control-Allow-Origin"] == "*"


def test_server_has_a_proxy_sized_backlog():
    """The default backlog of 5 resets connections when a proxy parallelises."""
    assert DashboardServer.request_queue_size >= 64
