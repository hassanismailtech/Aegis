"""Mock Upstream (PRD 5.7): OpenAI-shaped FastAPI app on :9000.

Echo mode answers "Transfer initiated to <first Placeholder seen>".
Tool mode returns a tool call whose arguments reuse Placeholders from the
prompt. Stores every received body in memory for GET /_tap.
Enables offline demos and zero API cost.
"""

import json
import re
import time
import uuid

from fastapi import FastAPI

app = FastAPI()
_bodies: list[dict] = []

_PLACEHOLDER = re.compile(r"\[\[[A-Z_]+_\d+\]\]")


def _placeholders(body: dict) -> list[str]:
    """Ordered unique Placeholders in message content and tool-call arguments."""
    texts: list[str] = []
    for message in body.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            texts.extend(part.get("text", "") for part in content if isinstance(part, dict))
        for call in message.get("tool_calls") or []:
            arguments = call.get("function", {}).get("arguments")
            if isinstance(arguments, str):
                texts.append(arguments)
    found: list[str] = []
    for match in _PLACEHOLDER.finditer("\n".join(texts)):
        if match.group(0) not in found:
            found.append(match.group(0))
    return found


def _used_tools(body: dict) -> set[str]:
    """Tool names already called in the conversation (demo loop progression)."""
    return {
        call["function"]["name"]
        for message in body.get("messages", [])
        for call in message.get("tool_calls") or []
        if isinstance(call.get("function"), dict)
    }


def _first(placeholders: list[str], entity_type: str) -> str | None:
    prefix = f"[[{entity_type}_"
    return next((placeholder for placeholder in placeholders if placeholder.startswith(prefix)), None)


def _tool_arguments(tool: dict, placeholders: list[str]) -> dict:
    """Reuse Placeholders from the prompt, mapped onto the tool's schema fields."""
    properties = tool.get("function", {}).get("parameters", {}).get("properties", {})
    if not properties:
        return {"placeholders": placeholders}
    arguments: dict = {}
    for field, schema in properties.items():
        name = field.lower()
        value = None
        for marker, entity_type in (
            ("account", "ACCOUNT_NO"),
            ("nuban", "ACCOUNT_NO"),
            ("name", "PERSON"),
            ("phone", "PHONE"),
            ("email", "EMAIL"),
            ("bvn", "BVN"),
            ("nin", "NIN"),
        ):
            if marker in name:
                value = _first(placeholders, entity_type)
                break
        if value is None and "amount" in name:
            value = 75000 if schema.get("type") in {"number", "integer"} else "75000"
        if value is not None:
            arguments[field] = value
    return arguments or {"placeholders": placeholders}


def _completion(model: str, message: dict, finish_reason: str, request: dict) -> dict:
    prompt_chars = sum(
        len(m.get("content"))
        for m in request.get("messages", [])
        if isinstance(m.get("content"), str)
    )
    prompt_tokens = prompt_chars // 4
    completion_payload = json.dumps(message)
    completion_tokens = max(1, len(completion_payload) // 4)
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@app.post("/v1/chat/completions")
async def chat_completions(body: dict) -> dict:
    _bodies.append(body)
    placeholders = _placeholders(body)
    model = body.get("model", "mock")
    used = _used_tools(body)
    tool = next(
        (
            candidate
            for candidate in body.get("tools") or []
            if candidate.get("function", {}).get("name") not in used
        ),
        None,
    )
    if tool is not None:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_" + uuid.uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": tool["function"]["name"],
                        "arguments": json.dumps(_tool_arguments(tool, placeholders)),
                    },
                }
            ],
        }
        return _completion(model, message, "tool_calls", body)
    target = placeholders[0] if placeholders else "(no placeholder)"
    return _completion(model, {"role": "assistant", "content": f"Transfer initiated to {target}"}, "stop", body)


@app.get("/_tap")
async def tap() -> list[dict]:
    return _bodies


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
