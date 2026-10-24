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
    """Ordered unique Placeholders in message content (format [[TYPE_N]])."""
    texts: list[str] = []
    for message in body.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            texts.extend(part.get("text", "") for part in content if isinstance(part, dict))
    found: list[str] = []
    for match in _PLACEHOLDER.finditer("\n".join(texts)):
        if match.group(0) not in found:
            found.append(match.group(0))
    return found


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
    if body.get("tools"):
        name = body["tools"][0].get("function", {}).get("name", "noop")
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_" + uuid.uuid4().hex,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps({"placeholders": placeholders})},
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
