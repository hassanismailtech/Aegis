"""Shared pytest hooks for Aegis."""

import json
import logging
import re
from datetime import datetime, timezone

import pytest
from redis import Redis

from app.config import settings
from app.telemetry import LEAKTEST_KEY


class _CaptureHandler(logging.Handler):
    """Collect Aegis log lines for the final no-PII-in-logs test."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(
            f"{record.levelname} {record.name} {record.getMessage()}"
        )


def pytest_configure(config: pytest.Config) -> None:
    logger = logging.getLogger("aegis")
    handler = _CaptureHandler()
    logger.addHandler(handler)
    config._aegis_log_handler = handler
    config._aegis_log_lines = handler.lines
    config._aegis_log_level = logger.level
    logger.setLevel(logging.INFO)


def pytest_unconfigure(config: pytest.Config) -> None:
    logger = logging.getLogger("aegis")
    handler = getattr(config, "_aegis_log_handler", None)
    if handler is not None:
        logger.removeHandler(handler)
    if hasattr(config, "_aegis_log_level"):
        logger.setLevel(config._aegis_log_level)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Run the log assertion after the leak and roundtrip traffic has happened."""
    for index, item in enumerate(items):
        if item.name == "test_no_planted_pii_in_any_log_line":
            items.append(items.pop(index))
            break


def pytest_addoption(parser: pytest.Parser) -> None:
    """`--report` persists the leak-test result for the dashboard (Step 5)."""
    parser.addoption(
        "--report",
        action="store_true",
        default=False,
        help="Write the leak-test result to Redis key aegis:leaktest.",
    )


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """Surface the leak-test line under plain `pytest -q` (PRD 3 demo script)."""
    line = getattr(config, "_aegis_leak_line", "")
    if line:
        terminalreporter.section("Aegis leak test", sep="=")
        terminalreporter.write_line(line)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Persist the final aggregate leak result after all test cleanup hooks."""
    if not session.config.getoption("--report"):
        return
    line = getattr(session.config, "_aegis_leak_line", "")
    match = re.fullmatch(r"leaks: (\d+) / (\d+) planted entities", line)
    if not match:
        return
    payload = {
        "leaks": int(match.group(1)),
        "planted": int(match.group(2)),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        redis.set(LEAKTEST_KEY, json.dumps(payload))
    finally:
        redis.close()
