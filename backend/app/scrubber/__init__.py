"""Scrubber (PRD 5.2): pattern → gazetteer → GLiNER, merged longest-wins,
Placeholders numbered by the Session Map.

scrub_messages() handles string content, list-of-parts content, assistant
tool_calls[].function.arguments (JSON string: scrub inside string values,
keep valid JSON) and tool message content. On ScrubError the caller blocks
the request (503, PRD 8); RedisError from Session Map claims propagates and
maps to 503 aegis_state_unavailable. Nothing pre-scrub is ever logged.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Sequence
from typing import Any

from app.config import settings
from app.detectors import Detector, Span, load_detectors
from app.errors import ScrubError
from app.schemas import EntityType
from app.session_map import SessionMap
from .ner import CHUNK_CHARS, GlinerNer

_PACK_DETECTORS: tuple[Detector, ...] = load_detectors(tuple(settings.detector_packs))
_PRIORITY = {
    EntityType.PHONE: 0,
    EntityType.EMAIL: 1,
    EntityType.NIN: 2,
    EntityType.ACCOUNT_NO: 3,
    EntityType.BVN: 4,
    EntityType.PERSON: 5,
}
_PLACEHOLDER_LOOKALIKE = re.compile(r"\[\[\s*[A-Za-z_]+_\d+\s*\]\]")


def _neutralize_placeholder_lookalikes(text: str) -> str:
    """Prevent client-supplied Placeholder syntax from addressing Session Map state."""
    return _PLACEHOLDER_LOOKALIKE.sub(
        lambda match: match.group(0).replace("[[", "[ [").replace("]]", "] ]"),
        text,
    )


def merge_spans(spans: list[Span]) -> list[Span]:
    """PRD 5.2: overlapping spans merged, longest wins, ties by layer priority."""
    keep: list[Span] = []
    for span in sorted(spans, key=lambda s: (-(s.end - s.start), s.start, _PRIORITY[s.type])):
        if all(span.end <= kept.start or span.start >= kept.end for kept in keep):
            keep.append(span)
    keep.sort(key=lambda span: (span.start, span.end))
    return keep


def ner_leftover(text: str, spans: list[Span]) -> list[str]:
    """PRD 9 fallback: NER runs only on text left after pattern + gazetteer.
    Detected spans are blanked (offsets preserved) and chunked at CHUNK_CHARS."""
    chars = list(text)
    for span in spans:
        chars[span.start : span.end] = " " * (span.end - span.start)
    blanked = "".join(chars)
    return [blanked[cut : cut + CHUNK_CHARS] for cut in range(0, len(blanked), CHUNK_CHARS)]


class _NerPersonDetector:
    """GLiNER PERSON layer over text left by earlier detectors (PRD 9)."""

    def __init__(self, ner: GlinerNer | None) -> None:
        self._ner = ner

    async def detect(self, text: str, prior: Sequence[Span]) -> list[Span]:
        if self._ner is None or not settings.ner_enabled:
            return []
        all_chunks = ner_leftover(text, list(prior))
        chunks = [
            (cut * CHUNK_CHARS, chunk)
            for cut, chunk in enumerate(all_chunks)
            if chunk.strip()
        ]
        try:
            ner_spans = await asyncio.wait_for(
                asyncio.to_thread(self._ner.find_persons, [chunk for _, chunk in chunks]),
                settings.ner_timeout_ms / 1000,
            )
        except TimeoutError:
            raise ScrubError(f"NER exceeded {settings.ner_timeout_ms} ms.") from None
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — fail closed without leaking inputs
            raise ScrubError("NER layer failed.") from exc
        spans: list[Span] = []
        for (base, _), found in zip(chunks, ner_spans, strict=True):
            spans.extend(
                Span(span.start + base, span.end + base, span.type, span.text)
                for span in found
            )
        return spans


async def _detect(text: str, ner: GlinerNer | None) -> list[Span]:
    """All Scrubber spans for one text: configured pack layers, then NER."""
    spans: list[Span] = []
    for detector in (*_PACK_DETECTORS, _NerPersonDetector(ner)):
        spans.extend(await detector.detect(text, spans))
    return merge_spans(spans)


async def detect_spans(text: str, ner: GlinerNer | None = None) -> list[Span]:
    """Full Scrubber detection for one text (bench/eval entry point)."""
    return await _detect(text, ner)


def _render(text: str, spans: list[Span], placeholders: list[str]) -> str:
    """Scrubbed string: disjoint spans replaced by their Placeholders."""
    parts: list[str] = []
    cursor = 0
    for span, placeholder in zip(spans, placeholders, strict=True):
        parts.append(text[cursor : span.start])
        parts.append(placeholder)
        cursor = span.end
    parts.append(text[cursor:])
    return "".join(parts)


async def _scrub_text(
    text: str,
    session_map: SessionMap,
    counts: dict[EntityType, int],
    ner: GlinerNer | None,
    context: str = "",
) -> str:
    """One plain string → scrubbed string (PRD 5.2).

    `context` prepends synthetic text for label matching (JSON key names, e.g.
    "account_no") without scrubbing it: spans must start after the prefix.
    """
    text = _neutralize_placeholder_lookalikes(text)
    spans = await _detect(context + text, ner) if context else await _detect(text, ner)
    if context:
        cut = len(context)
        spans = [
            Span(span.start - cut, span.end - cut, span.type, text[span.start - cut : span.end - cut])
            for span in spans
            if span.start >= cut
        ]
    if not spans:
        return text
    placeholders = [
        await session_map.get_or_create_placeholder(span.type, span.text) for span in spans
    ]
    for span, _ in zip(spans, placeholders, strict=True):
        counts[span.type] += 1
    return _render(text, spans, placeholders)


async def _scrub_json_value(value: Any, session_map: SessionMap, counts, ner, context: str = "") -> Any:
    """Scrub string values inside parsed JSON, keep the structure (PRD 5.1).
    Dict keys are passed as label context to their string values."""
    if isinstance(value, str):
        return await _scrub_text(value, session_map, counts, ner, context)
    if isinstance(value, dict):
        return {
            key: await _scrub_json_value(item, session_map, counts, ner, f"{key} ")
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [await _scrub_json_value(item, session_map, counts, ner, context) for item in value]
    return value


async def _scrub_arguments(
    raw: str, session_map: SessionMap, counts: dict[EntityType, int], ner: GlinerNer | None
) -> str:
    """tool_calls[].function.arguments: valid JSON in → valid JSON out."""
    try:
        data = json.loads(raw)
    except ValueError:
        return await _scrub_text(raw, session_map, counts, ner)  # not JSON: plain text
    return json.dumps(await _scrub_json_value(data, session_map, counts, ner))


async def _scrub_tool_call(
    tool_call: Any, session_map: SessionMap, counts: dict[EntityType, int], ner: GlinerNer | None
) -> Any:
    if not isinstance(tool_call, dict):
        return tool_call
    new = dict(tool_call)
    function = tool_call.get("function")
    if isinstance(function, dict) and isinstance(function.get("arguments"), str):
        new["function"] = {
            **function,
            "arguments": await _scrub_arguments(function["arguments"], session_map, counts, ner),
        }
    return new


async def _scrub_content_part(part: Any, session_map, counts, ner) -> Any:
    """List-of-parts content (PRD 5.1): scrub text parts, pass others through."""
    if (
        isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    ):
        return {**part, "text": await _scrub_text(part["text"], session_map, counts, ner)}
    return part


async def _scrub_message(
    message: Any, session_map: SessionMap, counts: dict[EntityType, int], ner: GlinerNer | None
) -> Any:
    if not isinstance(message, dict):
        return message
    new = dict(message)
    content = message.get("content")
    if isinstance(content, str):
        new["content"] = await _scrub_text(content, session_map, counts, ner)
    elif isinstance(content, list):
        new["content"] = [
            await _scrub_content_part(part, session_map, counts, ner) for part in content
        ]
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        new["tool_calls"] = [
            await _scrub_tool_call(call, session_map, counts, ner) for call in tool_calls
        ]
    return new


async def scrub_messages(
    messages: list[dict[str, Any]],
    session_map: SessionMap,
    ner: GlinerNer | None = None,
) -> tuple[list[dict[str, Any]], dict[EntityType, int], float]:
    """Scrub every message: (new_messages, entities per type, scrub_ms)."""
    started = time.perf_counter()
    counts: dict[EntityType, int] = {entity_type: 0 for entity_type in EntityType}
    scrubbed = [
        await _scrub_message(message, session_map, counts, ner) for message in messages
    ]
    return scrubbed, counts, (time.perf_counter() - started) * 1000
