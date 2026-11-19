"""Deployment isolation and real Caddy boundary behavior; no Docker needed here."""

import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_playground_compose_is_isolated() -> None:
    config = yaml.safe_load((ROOT / "deploy/compose.playground.yml").read_text())
    assert set(config["services"]) == {"aegis", "redis"}
    redis, proxy = (config["services"][key] for key in ("redis", "aegis"))
    assert "ports" not in redis and "volumes" not in redis
    assert redis["command"] == ["redis-server", "--save", "", "--appendonly", "no"]
    assert redis["tmpfs"] == ["/data"]
    assert proxy["ports"] == ["127.0.0.1:8000:8000"]
    assert proxy["read_only"] and proxy["tmpfs"] == ["/tmp"]
    assert "${SECLUME_IMAGE:?" in proxy["image"]
    env = proxy["environment"]
    assert env["PLAYGROUND_ENABLED"] == env["PLAYGROUND_TRUST_PROXY"] == "true"
    assert env["NER_ENABLED"] == "false" and not env["UPSTREAM_API_KEY"]
    assert env["AUDIT_DB_PATH"].startswith("/tmp/")
    assert env["BIND_HOST"] == "0.0.0.0" and env["FORWARDED_ALLOW_IPS"] == ""
    assert '"$$BIND_HOST"' in proxy["command"][-1]
    assert "--no-access-log --no-proxy-headers" in proxy["command"][-1]
    assert config["networks"]["private"]["internal"]


def test_real_caddy_requires_configured_host() -> None:
    env = {**os.environ, "PLAYGROUND_HOST": ""}
    result = subprocess.run([os.environ["CADDY_BIN"], "validate", "--config", str(ROOT / "deploy/Caddyfile"), "--adapter", "caddyfile"], env=env, capture_output=True, timeout=10)
    assert result.returncode != 0


def test_real_caddy_boundary(tmp_path: Path) -> None:
    binary = os.environ["CADDY_BIN"]  # mandatory in CI; never silently skipped
    forwarded = []

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            forwarded.append((self.headers.get("X-Forwarded-For"),
                              any(self.headers.get(key) for key in ("Authorization", "Cookie", "X-Upstream-Api-Key"))))
            self.send_response(429)
            self.send_header("Retry-After", "17")
            self.end_headers()

        do_OPTIONS = do_POST

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = tmp_path / "Caddyfile"
    config.write_text((ROOT / "deploy/Caddyfile").read_text().replace("127.0.0.1:8000", f"127.0.0.1:{server.server_port}"))
    env = {**os.environ, "PLAYGROUND_HOST": f"http://127.0.0.1:{port}"}
    process = None
    try:
        check = subprocess.run([binary, "validate", "--config", str(config), "--adapter", "caddyfile"], env=env, capture_output=True, timeout=10)
        assert check.returncode == 0, "Caddy configuration validation failed"
        process = subprocess.Popen([binary, "run", "--config", str(config), "--adapter", "caddyfile"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with httpx.Client(base_url=env["PLAYGROUND_HOST"], trust_env=False, timeout=2) as client:
            for _ in range(50):
                try:
                    if client.get("/").status_code == 404:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Caddy did not become ready")
            for path in ("/", "/readyz", "/docs", "/v1/chat/completions", "/v1/aegis/events", "/v1/playground/scrub/extra"):
                assert client.post(path).status_code == 404
            assert client.get("/v1/playground/scrub").status_code == 404
            assert not forwarded
            for method in ("POST", "OPTIONS"):
                response = client.request(method, "/v1/playground/scrub", headers={"X-Forwarded-For": "192.0.2.1", "Authorization": "private-marker", "Cookie": "private-marker", "X-Upstream-Api-Key": "private-marker"})
                assert response.status_code == 429
                assert response.headers["Retry-After"] == "17"
                assert response.headers["Access-Control-Expose-Headers"] == "Retry-After"
            assert forwarded == [("127.0.0.1", False), ("127.0.0.1", False)]
            server.shutdown()
            server.server_close()
            assert client.post("/v1/playground/scrub?private-marker").status_code == 502
    finally:
        if process is not None:
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert b"private-marker" not in stdout + stderr
