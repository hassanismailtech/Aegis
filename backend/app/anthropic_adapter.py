"""Anthropic Messages adapter: content blocks → Scrubber/Reinjector.

The Scrubber and Reinjector only know text and JSON values. This module walks
Anthropic blocks (text, tool_use input, tool_result content) and delegates all
detection, Placeholder numbering and tolerant matching to those modules, so
the Messages route reuses the same logic as `/v1/chat/completions`.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from app.reinjector import Reinjector
from app.schemas import EntityType
from app.scrubber import scrub_json_value, scrub_text
from app.scrubber.ner import GlinerNer
from app.session_map import SessionMap


async def _scrub_block(
    block: Any,
    session_map: SessionMap,
    counts: dict[EntityType, int],
    ner: GlinerNer | None,
) -> Any:
    if not isinstance(block, dict):
        return block
    kind = block.get("type")
    if kind == "text" and isinstance(block.get("text"), str):
        return {**block, "text": await scrub_text(block["text"], session_map, counts, ner)}
    if kind == "tool_use":
        value = block.get("input")
        if isinstance(value, (dict, list)):
            return {**block, "input": await scrub_json_value(value, session_map, counts, ner)}
        if isinstance(value, str):
            return {**block, "input": await scrub_text(value, session_map, counts, ner)}
    if kind == "tool_result":
        content = block.get("content")
        if isinstance(content, str):
            return {**block, "content": await scrub_text(content, session_map, counts, ner)}
        if isinstance(content, list):
            return {
                **block,
                "content": [
                    await _scrub_block(part, session_map, counts, ner) for part in content
                ],
            }
    return block


async def _scrub_system(
    system: Any,
    session_map: SessionMap,
    counts: dict[EntityType, int],
    ner: GlinerNer | None,
) -> Any:
    if isinstance(system, str):
        return await scrub_text(system, session_map, counts, ner)
    if isinstance(system, list):
        return [await _scrub_block(block, session_map, counts, ner) for block in system]
    return system


async def scrub_request(
    payload: dict[str, Any],
    session_map: SessionMap,
    ner: GlinerNer | None,
) -> tuple[dict[str, Any], dict[EntityType, int], float]:
    """Scrub every outbound text/tool value: (new payload, counts, scrub_ms)."""
    started = time.perf_counter()
    counts: dict[EntityType, int] = {entity_type: 0 for entity_type in EntityType}
    outbound = dict(payload)
    if "system" in payload:
        outbound["system"] = await _scrub_system(payload["system"], session_map, counts, ner)

    messages: list[Any] = []
    for message in payload["messages"]:
        if not isinstance(message, dict):
            messages.append(message)
            continue
        new = dict(message)
        content = message.get("content")
        if isinstance(content, str):
            new["content"] = await scrub_text(content, session_map, counts, ner)
        elif isinstance(content, list):
            new["content"] = [
                await _scrub_block(block, session_map, counts, ner) for block in content
            ]
        messages.append(new)
    outbound["messages"] = messages
    return outbound, counts, (time.perf_counter() - started) * 1000


def reinject_response(response: dict[str, Any], forward: Mapping[str, str]) -> int:
    """Swap Placeholders in content text and tool_use input; returns unresolved."""
    reinjector = Reinjector(forward)
    content = response.get("content")
    if isinstance(content, str):
        response["content"] = reinjector.content(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and isinstance(block.get("text"), str):
                block["text"] = reinjector.content(block["text"])
            elif kind == "tool_use":
                value = block.get("input")
                if isinstance(value, (dict, list)):
                    block["input"] = reinjector.json_value(value)
                elif isinstance(value, str):
                    block["input"] = reinjector.content(value)
    return reinjector.unresolved


def usage_tokens(usage: Mapping[str, Any] | None) -> dict[str, int] | None:
    """Anthropic usage → the prompt/completion shape telemetry fee math uses."""
    if not usage:
        return None
    return {
        "prompt_tokens": int(usage.get("input_tokens") or 0),
        "completion_tokens": int(usage.get("output_tokens") or 0),
    }
