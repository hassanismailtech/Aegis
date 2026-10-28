"""Reinjector (PRD 5.4): swaps Placeholders in a completion back to originals.

Places: choices[].message.content and choices[].message.tool_calls[]
.function.arguments. Only Placeholders present in this Session's Session Map
are swapped; unknown ones are left untouched and counted as `unresolved`
(request status becomes state_loss, HTTP stays 200, PRD 8).

Matching is tolerant per PRD 7.1: brackets, casing and inner spaces may vary
(`[[PERSON_1]]`, `[[ PERSON_1 ]]`, `[[person_1]]`, `[PERSON_1]`,
`[ PERSON_1 ]`, possessives and markdown runs resolve to the Map entry),
while non-Placeholder text like `[1]` is never touched.

For tool-call `arguments` (a JSON string) the replacement is JSON-escaped so
the string still parses as JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

# Open bracket (`[[`/`[`), optional padding space, TYPE (letters/underscores),
# `_`, number, optional padding space, close bracket (`]]`/`]`) — all four
# bracket/pad combinations tolerate, PRD 7.1. `type` backtracks to allow
# multi-part types like ACCOUNT_NO before the final `_N`.
_PLACEHOLDER = re.compile(r"\[\[? ?(?P<type>[A-Za-z_]+)_(?P<n>\d+) ?\]\]?")


def _canonical(match: re.Match[str]) -> str:
    """Exact Session Map key for a tolerant match (PLACEHOLDER format, PRD 7.1)."""
    return f"[[{match['type'].upper()}_{match['n']}]]"


class Reinjector:
    """Stateful for one response: every failed swap increments `unresolved`."""

    def __init__(self, forward: Mapping[str, str]) -> None:
        """`forward`: Placeholder -> original from the Session Map (PRD 7.2)."""
        self.forward = dict(forward)
        self.unresolved = 0

    def content(self, text: str) -> str:
        """Plain text (message content): replacements inserted verbatim."""
        return self._swap(text, json_escape=False)

    def arguments(self, arguments: str) -> str:
        """JSON string (function arguments): replacements JSON-escaped."""
        return self._swap(arguments, json_escape=True)

    def json_value(self, value: Any) -> Any:
        """Walk a parsed JSON value (e.g. Anthropic tool_use input); string leaves
        are swapped verbatim because the caller will serialize the structure."""
        if isinstance(value, str):
            return self.content(value)
        if isinstance(value, dict):
            return {key: self.json_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.json_value(item) for item in value]
        return value

    def _swap(self, text: str, *, json_escape: bool) -> str:
        counter = self

        def replace(match: re.Match[str]) -> str:
            original = self.forward.get(_canonical(match))
            if original is None:
                counter.unresolved += 1  # PRD 5.4: unknown stays as-is, counts
                return match[0]
            if json_escape:
                return json.dumps(original)[1:-1]  # escaped, still valid JSON
            return original

        return _PLACEHOLDER.sub(replace, text)

    def inject(self, completion: dict[str, Any]) -> dict[str, Any]:
        """Swap in place across every choice; returns the same structure."""
        for choice in completion.get("choices") or []:
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                continue
            if isinstance(message.get("content"), str):
                message["content"] = self.content(message["content"])
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    function = call.get("function") if isinstance(call, dict) else None
                    if isinstance(function, dict) and isinstance(function.get("arguments"), str):
                        function["arguments"] = self.arguments(function["arguments"])
        return completion
