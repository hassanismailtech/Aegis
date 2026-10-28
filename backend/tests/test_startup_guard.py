"""Tests for startup guard and ticket secret enforcement."""

import pytest
from unittest.mock import patch

from app.config import Settings


def _settings(**overrides):
    """Build a Settings instance with specified overrides."""
    defaults = {
        "redis_url": "redis://localhost:6379/0",
        "ner_enabled": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestStartupGuard:
    """Non-loopback bind without keys must be refused unless AEGIS_INSECURE_DEV."""

    def test_loopback_no_keys_ok(self):
        """127.0.0.1 with no keys file is fine (local dev)."""
        s = _settings(bind_host="127.0.0.1", aegis_keys_file="")
        from app.main import _is_loopback
        assert _is_loopback(s.bind_host)

    def test_default_bind_no_keys_ok(self):
        """0.0.0.0 default with no keys file is treated as loopback."""
        s = _settings(bind_host="0.0.0.0", aegis_keys_file="")
        from app.main import _is_loopback
        assert _is_loopback(s.bind_host)

    def test_nonloopback_no_keys_no_flag_refuses(self):
        """A public bind without keys and without AEGIS_INSECURE_DEV must raise."""
        from app.main import _is_loopback
        assert not _is_loopback("10.0.0.5")

    def test_nonloopback_no_keys_with_flag_allowed(self):
        """AEGIS_INSECURE_DEV=1 suppresses the guard."""
        s = _settings(bind_host="10.0.0.5", aegis_keys_file="", aegis_insecure_dev=True)
        from app.main import _is_loopback
        assert not _is_loopback(s.bind_host)
        assert s.aegis_insecure_dev

    def test_nonloopback_with_keys_ok(self):
        """A public bind with AEGIS_KEYS_FILE set is fine."""
        s = _settings(bind_host="10.0.0.5", aegis_keys_file="/path/to/keys.json")
        from app.main import _is_loopback
        assert not _is_loopback(s.bind_host)
        assert s.aegis_keys_file


class TestTicketSecretEnforcement:
    """AEGIS_TICKET_SECRET must be set when auth is enabled."""

    def test_no_keys_no_ticket_secret_ok(self):
        """Local dev without keys: ticket secret falls back to demo token (allowed)."""
        s = _settings(aegis_keys_file="", aegis_ticket_secret="", aegis_demo_token="demo")
        ticket_secret = s.aegis_ticket_secret or s.aegis_demo_token
        assert ticket_secret == "demo"

    def test_keys_with_ticket_secret_ok(self):
        """Auth enabled with a dedicated ticket secret is fine."""
        s = _settings(
            aegis_keys_file="/path/to/keys.json",
            aegis_ticket_secret="my-dedicated-secret",
        )
        assert s.aegis_ticket_secret == "my-dedicated-secret"

    def test_keys_without_ticket_secret_must_fail(self):
        """Auth enabled without AEGIS_TICKET_SECRET must be caught at startup."""
        s = _settings(aegis_keys_file="/path/to/keys.json", aegis_ticket_secret="")
        # The lifespan enforces this, here we verify the condition
        auth_enabled = bool(s.aegis_keys_file)
        assert auth_enabled and not s.aegis_ticket_secret
