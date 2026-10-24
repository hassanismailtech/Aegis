"""Shared pytest hooks for Aegis."""

import pytest


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """Surface the leak-test line under plain `pytest -q` (PRD 3 demo script)."""
    line = getattr(config, "_aegis_leak_line", "")
    if line:
        terminalreporter.section("Aegis leak test", sep="=")
        terminalreporter.write_line(line)
