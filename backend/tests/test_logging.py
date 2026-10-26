"""Log-capture test: no planted PII or credentials may appear in Aegis logs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROMPTS_PATH = Path(__file__).resolve().parents[2] / "demo" / "prompts.json"

_ROUNDTRIP_VALUES = [
    "Chinedu Okafor",
    "22334455667",
    "0803 123 4567",
    "08031234567",
    "0123456789",
    "ada@obi.ng",
]
_CREDENTIALS = ["sk-client", "test-secret", "key-a", "key-b"]


def test_no_planted_pii_in_any_log_line(pytestconfig: pytest.Config) -> None:
    lines = list(getattr(pytestconfig, "_aegis_log_lines", []))
    assert lines, "no Aegis log lines were captured"
    assert any('"event":"request"' in line for line in lines), "no structured request logs"

    prompts = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    planted = [value for prompt in prompts for value in prompt["planted"]]
    forbidden = sorted(set(planted + _ROUNDTRIP_VALUES + _CREDENTIALS))
    leaks = [value for value in forbidden if any(value in line for line in lines)]
    assert not leaks, "forbidden values appeared in logs: " + ", ".join(leaks)
