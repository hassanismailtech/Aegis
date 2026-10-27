"""`aegis doctor` checks and output (no real network or model warm-up)."""

import pytest

from app import cli


def test_safe_url_strips_credentials() -> None:
    assert (
        cli._safe_url("redis://user:secret@example.com:6379/0")
        == "redis://example.com:6379/0"
    )
    assert "secret" not in cli._safe_url("https://user:secret@api.openai.com/v1")


def test_doctor_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    async def checks() -> list[cli.Check]:
        return [
            cli.Check("redis", True, "redis://127.0.0.1:6379/0 (Redis 7)"),
            cli.Check("model", True, "urchade/gliner_small-v2.1 warm (threshold 0.5)"),
            cli.Check("upstream", True, "http://127.0.0.1:9000/v1 reachable (HTTP 404)"),
        ]

    monkeypatch.setattr(cli, "_run_checks", checks)
    monkeypatch.setattr(cli, "_versions", lambda: {"python": "3.12", "aegis": "0.1.0"})
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "Aegis doctor" in out
    assert "aegis" in out and "0.1.0" in out
    assert "redis" in out and "model" in out and "upstream" in out


def test_doctor_failure_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def checks() -> list[cli.Check]:
        return [cli.Check("redis", False, "redis://127.0.0.1:6379/0 unreachable")]

    monkeypatch.setattr(cli, "_run_checks", checks)
    monkeypatch.setattr(cli, "_versions", lambda: {"aegis": "0.1.0"})
    assert cli.main(["doctor"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_doctor_requires_a_command() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


def test_check_model_is_ok_when_ner_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.settings, "ner_enabled", False)
    result = cli.check_model()
    assert result.ok
    assert "NER disabled" in result.detail
