"""Claims rules, narrow exemptions, source selection, and safe CLI output."""

from pathlib import Path

import pytest

from scripts import claims_lint


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(("text", "rule"), [
    ("We guarantee protection.", "guarantee"),
    ("GUARANTEED protection", "guarantee"),
    ("This guarantees protection.", "guarantee"),
    ("zero-knowledge", "zero_knowledge"),
    ("ZERO KNOWLEDGE", "zero_knowledge"),
    ("100% recall", "absolute_quality"),
    ("100% PRECISION", "absolute_quality"),
    ("100%  accuracy", "absolute_quality"),
    ("<40ms", "unqualified_latency"),
    ("< 40 ms", "unqualified_latency"),
    ("mathematically private", "mathematical_assurance"),
    ("legally compliant", "legal_compliance"),
    ("without violating the rules", "transfer_legality"),
    ("military-grade", "military_grade"),
    ("three milliseconds", "unmeasured_latency"),
])
def test_banned_claims(tmp_path: Path, text: str, rule: str) -> None:
    write(tmp_path, "README.md", "Measured results.\n" + text)
    assert claims_lint.scan(tmp_path) == [claims_lint.Finding(Path("README.md"), 2, rule)]


def test_multiple_rules_on_one_line(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "Guarantees 100% accuracy in three milliseconds.")
    assert {finding.rule for finding in claims_lint.scan(tmp_path)} == {
        "guarantee", "absolute_quality", "unmeasured_latency",
    }


def test_allow_marker_is_line_scoped(tmp_path: Path) -> None:
    write(tmp_path, "docs/style.md", 'Never say "guaranteed". <!-- claims-lint: allow -->\nWe guarantee protection.')
    assert claims_lint.scan(tmp_path) == [claims_lint.Finding(Path("docs/style.md"), 2, "guarantee")]


def test_prd_quote_exemption_is_exact_and_file_scoped(tmp_path: Path) -> None:
    quote = (
        '- **Honest claim:** Aegis reduces leakage. It does not "guarantee zero". '
        "Structured IDs are rule-detected. Names are model-detected, with recall we measure and show."
    )
    write(tmp_path, "docs/PRD.md", quote + "\n" + quote + " We guarantee protection.\nNew guarantee.")
    write(tmp_path, "docs/other.md", quote)
    assert {(f.path.as_posix(), f.line) for f in claims_lint.scan(tmp_path)} == {
        ("docs/PRD.md", 2), ("docs/PRD.md", 3), ("docs/other.md", 1),
    }


@pytest.mark.parametrize("name", [
    "README.md", "docs/guide.md", "docs/nested/guide.md", "docs/nested/CLAIMS.md",
    "website/app/page.tsx", "website/lib/content.ts", "website/public/copy.json",
    "website/public/page.html", "website/article.mdx", "website/public/copy.txt",
    "website/public/art.svg", "website/app/globals.css", "website/component.jsx",
    "website/app/build/page.tsx",
])
def test_public_source_selection(tmp_path: Path, name: str) -> None:
    write(tmp_path, name, "We guarantee protection.")
    assert [f.path.as_posix() for f in claims_lint.scan(tmp_path)] == [name]


@pytest.mark.parametrize("name", [
    "docs/CLAIMS.md", "NOTES.md", "backend/tests/example.py",
    "website/node_modules/vendor/index.ts", "website/.next/server/app.js",
    "website/out/index.html", "website/dist/index.js", "website/build/app.js",
    "website/coverage/index.html", "website/.vercel/output/index.html",
    "website/package-lock.json", "website/npm-shrinkwrap.json",
])
def test_generated_and_out_of_scope_files_are_excluded(tmp_path: Path, name: str) -> None:
    write(tmp_path, name, "We guarantee protection.")
    assert claims_lint.scan(tmp_path) == []


def test_qualified_copy_and_literal_regex_characters(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "Measured on synthetic data; detection has limits.\n.* [a-z]+ (a+)+")
    assert claims_lint.scan(tmp_path) == []


def test_cli_failure_contains_metadata_only(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    text = "Private example text: we guarantee protection."
    write(tmp_path, "README.md", text)
    assert claims_lint.main(tmp_path) == 1
    output = capsys.readouterr()
    assert output.out == "README.md:1: guarantee\nClaims lint failed: 1 violation(s).\n"
    assert text not in output.out


def test_cli_success(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    write(tmp_path, "README.md", "Measured on a synthetic set.")
    assert claims_lint.main(tmp_path) == 0
    assert capsys.readouterr().out == "Claims lint passed.\n"


def test_unreadable_source_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    write(tmp_path, "README.md", "Measured on a synthetic set.")
    path = write(tmp_path, "website/app/page.tsx", "")
    path.write_bytes(b"\xff")
    assert claims_lint.main(tmp_path) == 2
    assert capsys.readouterr().err == "Claims lint error: source files unreadable.\n"


def test_missing_source_root_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert claims_lint.main(tmp_path) == 2
    assert capsys.readouterr().err == "Claims lint error: source files unreadable.\n"
