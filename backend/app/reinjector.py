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
from collections.abc import Callable, Hashable, Mapping
from typing import Any

# Open bracket (`[[`/`[`), optional padding space, TYPE (letters/underscores),
# `_`, number, optional padding space, close bracket (`]]`/`]`) — all four
# bracket/pad combinations tolerate, PRD 7.1. `type` backtracks to allow
# multi-part types like ACCOUNT_NO before the final `_N`.
_PLACEHOLDER = re.compile(r"\[\[? ?(?P<type>[A-Za-z_]+)_(?P<n>\d+) ?\]\]?")

HOLDBACK_CHARS = 40

# Suffix that could still become a Placeholder once more characters arrive.
# Includes a completed `]` because `[[PERSON_1]` is itself a tolerant form and
# one more `]` may still follow; holding it until the next chunk is harmless.
_PARTIAL = re.compile(r"\[\[? ?[A-Za-z_]*(?:_\d*)? ?\]?\]?$")


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


def _hold_from(text: str) -> int:
    """Start of a suffix that may still become a Placeholder, or len(text).

    Only the last `HOLDBACK_CHARS` characters matter: an older opener would be
    flushed by the cap anyway, so the scan is bounded regardless of chunk size.
    Leftmost matching suffix wins: in `[[PERSON_1` the first `[` opens the
    Placeholder (the second alone would leak a literal `[`); an earlier `[see`
    cannot match the partial grammar, so a later Placeholder still wins.
    """
    position = text.find("[", max(0, len(text) - HOLDBACK_CHARS))
    while position != -1:
        if _PARTIAL.match(text, position):
            return position
        position = text.find("[", position + 1)
    return len(text)


class StreamingReinjector:
    """Reinjector for chunked output (OpenAI/Anthropic SSE).

    A Placeholder may be split at any character boundary. Text is held while
    its tail could still become a Placeholder, released as soon as following
    text proves it cannot, and flushed as-is if the tail reaches
    `HOLDBACK_CHARS` so memory stays bounded. Held tail bytes are never dropped.
    A completed Placeholder is swapped by the same `Reinjector` used for
    non-streaming replies.
    """

    def __init__(self, forward: Mapping[str, str]) -> None:
        self._injector = Reinjector(forward)
        self._text: dict[Hashable, str] = {}
        self._arguments: dict[Hashable, str] = {}

    @property
    def unresolved(self) -> int:
        return self._injector.unresolved

    def feed_text(self, key: Hashable, chunk: str) -> str:
        """Append a content fragment; return the safe-to-send prefix."""
        self._text[key] = self._text.get(key, "") + chunk
        return self._drain(self._text, key, self._injector.content)

    def flush_text(self, key: Hashable) -> str:
        """Flush any held content tail (at block/chunk end)."""
        return self._finish(self._text, key, self._injector.content)

    def feed_arguments(self, key: Hashable, chunk: str) -> str:
        """Append a tool-arguments fragment; replacements stay JSON-escaped."""
        self._arguments[key] = self._arguments.get(key, "") + chunk
        return self._drain(self._arguments, key, self._injector.arguments)

    def flush_arguments(self, key: Hashable) -> str:
        """Flush any held tool-arguments tail."""
        return self._finish(self._arguments, key, self._injector.arguments)

    def json_value(self, value: Any) -> Any:
        """Non-streamed JSON value (e.g. a non-empty tool_use start block)."""
        return self._injector.json_value(value)

    @staticmethod
    def _drain(
        buffers: dict[Hashable, str], key: Hashable, swap: Callable[[str], str]
    ) -> str:
        text = buffers.get(key, "")
        if not text:
            return ""
        hold_at = _hold_from(text)
        if hold_at < len(text) and len(text) - hold_at <= HOLDBACK_CHARS:
            buffers[key] = text[hold_at:]
            return swap(text[:hold_at])
        buffers.pop(key, None)
        return swap(text)

    @staticmethod
    def _finish(
        buffers: dict[Hashable, str], key: Hashable, swap: Callable[[str], str]
    ) -> str:
        text = buffers.pop(key, "")
        return swap(text) if text else ""
