"""Lexical guard for public claims; diagnostics contain source ids only."""

import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ALLOW_MARKER = "claims-lint: allow"
_EXTENSIONS = {".md", ".mdx", ".ts", ".tsx", ".js", ".jsx", ".json", ".html", ".txt", ".css", ".svg"}
_IGNORED_DIRS = {"node_modules", ".next", ".git", ".vercel"}
_OUTPUT_DIRS = {"out", "dist", "build", "coverage"}
_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json"}
_RULES = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in [
    ("guarantee", r"\bguarantee[sd]?\b"),
    ("zero_knowledge", r"\bzero[- ]knowledge\b"),
    ("absolute_quality", r"\b100%\s+(recall|precision|accuracy)\b"),
    ("unqualified_latency", r"<\s*40\s*ms\b"),
    ("mathematical_assurance", r"\bmathematically\b"),
    ("legal_compliance", r"\blegally\s+compliant\b"),
    ("transfer_legality", r"\bwithout\s+violating\b"),
    ("military_grade", r"\bmilitary-grade\b"),
    ("unmeasured_latency", r"\bthree\s+milliseconds\b"),
])
# This exact archived quotation is reviewed; the PRD must remain unchanged.
_PRD_QUOTE = (
    '- **Honest claim:** Aegis reduces leakage. It does not "guarantee zero". '
    "Structured IDs are rule-detected. Names are model-detected, with recall we measure and show."
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str


def source_files(root: Path) -> Iterator[Path]:
    readme = root / "README.md"
    if readme.is_file() and not readme.is_symlink():
        yield readme
    for path in sorted((root / "docs").rglob("*.md")):
        if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() != "docs/CLAIMS.md":
            yield path
    for directory, dirs, files in os.walk(root / "website", followlinks=False):
        ignored = _IGNORED_DIRS | (_OUTPUT_DIRS if Path(directory) == root / "website" else set())
        dirs[:] = sorted(name for name in dirs if name not in ignored)
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix in _EXTENSIONS and name not in _LOCKFILES and not path.is_symlink():
                yield path


def scan(root: Path) -> list[Finding]:
    findings = []
    for path in source_files(root):
        relative = path.relative_to(root)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _ALLOW_MARKER in line:
                continue
            if relative.as_posix() == "docs/PRD.md" and line == _PRD_QUOTE:
                continue
            for rule, pattern in _RULES:
                if pattern.search(line):
                    findings.append(Finding(relative, number, rule))
    return findings


def main(root: Path = ROOT) -> int:
    try:
        if not (root / "README.md").is_file():
            raise OSError("Source root unavailable.")
        findings = scan(root)
    except (OSError, UnicodeError):
        print("Claims lint error: source files unreadable.", file=sys.stderr)
        return 2
    for finding in findings:
        print(f"{finding.path.as_posix()}:{finding.line}: {finding.rule}")
    if findings:
        print(f"Claims lint failed: {len(findings)} violation(s).")
        return 1
    print("Claims lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
