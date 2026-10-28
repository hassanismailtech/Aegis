"""Protocol streaming: SSE parsing and chunk-by-chunk Placeholder reinjection.

Both Upstream protocols are translated here so the route only wires transport,
telemetry and the Reinjector. The OpenAI rewriter handles `choices[].delta`
content/tool arguments and `n > 1`; the Anthropic rewriter handles text deltas,
`input_json_delta` and per-block flush ordering.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.reinjector import StreamingReinjector


async def sse_events(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str | None, str]]:
    """Group SSE lines into (event, data); data lines are joined per SSE spec."""
    event: str | None = None
    data: list[str] = []
    async for line in lines:
        if line == "":
            if data:
                yield event, "\n".join(data)
            event = None
            data = []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if data:
        yield event, "\n".join(data)


def format_sse(event: str | None, data: str) -> bytes:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n".encode()


def _openai_chunk(template: dict[str, Any], choices: list[dict[str, Any]]) -> dict[str, Any]:
    chunk = {key: value for key, value in template.items() if key != "choices"}
    chunk.setdefault("object", "chat.completion.chunk")
    chunk["choices"] = choices
    return chunk


class OpenAIStreamRewriter:
    """Reinject OpenAI chat-completion SSE chunks, buffer per choice/tool call."""

    def __init__(self, forward: dict[str, str]) -> None:
        self._reinjector = StreamingReinjector(forward)
        self._meta: dict[str, Any] = {}
        self._choices: set[int] = set()
        self._tool_calls: dict[int, set[int]] = {}
        self.usage: dict[str, Any] | None = None

    @property
    def unresolved(self) -> int:
        return self._reinjector.unresolved

    def rewrite(self, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        self._meta = chunk
        usage = chunk.get("usage")
        if isinstance(usage, dict):
            self.usage = usage
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return [chunk]
        emitted: list[dict[str, Any]] = []
        for choice in choices:
            if not isinstance(choice, dict):
                emitted.append(chunk)
                continue
            index = int(choice.get("index", 0))
            self._choices.add(index)
            delta = choice.get("delta")
            rewritten = dict(delta) if isinstance(delta, dict) else {}
            content = rewritten.get("content")
            if isinstance(content, str):
                safe = self._reinjector.feed_text(index, content)
                if safe:
                    rewritten["content"] = safe
                else:
                    rewritten.pop("content", None)
            tool_calls = rewritten.get("tool_calls")
            if isinstance(tool_calls, list):
                rewritten["tool_calls"] = [
                    self._rewrite_tool_call(index, call) for call in tool_calls
                ]
            finish = choice.get("finish_reason")
            if finish is None:
                emitted.append(_openai_chunk(chunk, [{**choice, "delta": rewritten}]))
                continue
            if rewritten:
                emitted.append(
                    _openai_chunk(chunk, [{**choice, "delta": rewritten, "finish_reason": None}])
                )
            emitted.extend(self._flush_choice(chunk, index))
            body = {
                key: value
                for key, value in choice.items()
                if key not in ("delta", "finish_reason")
            }
            emitted.append(
                _openai_chunk(chunk, [{**body, "delta": {}, "finish_reason": finish}])
            )
        return emitted

    def _rewrite_tool_call(self, choice: int, call: Any) -> Any:
        if not isinstance(call, dict):
            return call
        rewritten = dict(call)
        function = rewritten.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("arguments"), str):
            return rewritten
        tool_index = int(call.get("index", 0))
        self._tool_calls.setdefault(choice, set()).add(tool_index)
        safe = self._reinjector.feed_arguments((choice, tool_index), function["arguments"])
        new_function = dict(function)
        if safe:
            new_function["arguments"] = safe
        else:
            new_function.pop("arguments", None)
        rewritten["function"] = new_function
        return rewritten

    def _flush_choice(
        self, template: dict[str, Any], index: int
    ) -> list[dict[str, Any]]:
        emitted: list[dict[str, Any]] = []
        text = self._reinjector.flush_text(index)
        if text:
            emitted.append(
                _openai_chunk(
                    template,
                    [{"index": index, "delta": {"content": text}, "finish_reason": None}],
                )
            )
        for tool_index in sorted(self._tool_calls.get(index, ())):
            arguments = self._reinjector.flush_arguments((index, tool_index))
            if arguments:
                emitted.append(
                    _openai_chunk(
                        template,
                        [
                            {
                                "index": index,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": tool_index,
                                            "function": {"arguments": arguments},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    )
                )
        return emitted

    def flush_all(self) -> list[dict[str, Any]]:
        """Flush every held tail, e.g. when `[DONE]` arrives without a finish."""
        emitted: list[dict[str, Any]] = []
        for index in sorted(self._choices):
            emitted.extend(self._flush_choice(self._meta, index))
        return emitted


class AnthropicStreamRewriter:
    """Reinject Anthropic Messages SSE events in place, per content block."""

    def __init__(self, forward: dict[str, str]) -> None:
        self._reinjector = StreamingReinjector(forward)
        self._indices: set[int] = set()
        self.input_tokens = 0
        self.output_tokens = 0
        self.failed = False

    @property
    def unresolved(self) -> int:
        return self._reinjector.unresolved

    def usage(self) -> dict[str, int]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}

    def rewrite(
        self, event: str | None, data: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        kind = str(data.get("type") or event or "message")
        if kind == "message_start":
            message = data.get("message")
            if isinstance(message, dict):
                self._usage(message.get("usage"))
        elif kind == "message_delta":
            self._usage(data.get("usage"))
        elif kind == "content_block_start":
            return self._start_block(kind, data)
        elif kind == "content_block_delta":
            rewritten = self._delta(kind, data)
            return [rewritten] if rewritten is not None else []
        elif kind == "content_block_stop":
            index = int(data.get("index", 0))
            return self._flush_block(index) + [(kind, data)]
        elif kind == "message_stop":
            return self._flush_all() + [(kind, data)]
        elif kind == "error":
            self.failed = True
        return [(kind, data)]

    def _usage(self, usage: Any) -> None:
        if not isinstance(usage, dict):
            return
        if usage.get("input_tokens") is not None:
            self.input_tokens = int(usage["input_tokens"])
        if usage.get("output_tokens") is not None:
            self.output_tokens = int(usage["output_tokens"])

    def _start_block(
        self, kind: str, data: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        index = int(data.get("index", 0))
        self._indices.add(index)
        block = data.get("content_block")
        if not isinstance(block, dict):
            return [(kind, data)]
        block_type = str(block.get("type") or "")
        rewritten = dict(block)
        if block_type == "text" and isinstance(block.get("text"), str) and block["text"]:
            rewritten["text"] = self._reinjector.feed_text(index, block["text"])
        elif block_type == "tool_use" and isinstance(block.get("input"), (dict, list)):
            if block["input"]:
                rewritten["input"] = self._reinjector.json_value(block["input"])
        return [(kind, {**data, "content_block": rewritten})]

    def _delta(
        self, kind: str, data: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        index = int(data.get("index", 0))
        self._indices.add(index)
        delta = data.get("delta")
        if not isinstance(delta, dict):
            return kind, data
        delta_type = delta.get("type")
        if delta_type == "text_delta" and isinstance(delta.get("text"), str):
            safe = self._reinjector.feed_text(index, delta["text"])
            if not safe:
                return None
            return kind, {**data, "delta": {**delta, "text": safe}}
        if delta_type == "input_json_delta" and isinstance(delta.get("partial_json"), str):
            safe = self._reinjector.feed_arguments(index, delta["partial_json"])
            if not safe:
                return None
            return kind, {**data, "delta": {**delta, "partial_json": safe}}
        return kind, data

    def _flush_block(self, index: int) -> list[tuple[str, dict[str, Any]]]:
        emitted: list[tuple[str, dict[str, Any]]] = []
        text = self._reinjector.flush_text(index)
        if text:
            emitted.append(
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": index,
                        "delta": {"type": "text_delta", "text": text},
                    },
                )
            )
        arguments = self._reinjector.flush_arguments(index)
        if arguments:
            emitted.append(
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": index,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": arguments,
                        },
                    },
                )
            )
        return emitted

    def _flush_all(self) -> list[tuple[str, dict[str, Any]]]:
        emitted: list[tuple[str, dict[str, Any]]] = []
        for index in sorted(self._indices):
            emitted.extend(self._flush_block(index))
        return emitted
