"""Demo agent (PRD 5.7): official OpenAI SDK -> Aegis -> Upstream.

Runs a two-tool task against the hardcoded CUSTOMERS array, then prints
AGENT SAW (the client transcript, real values) and UPSTREAM SAW (the Wire Tap,
Placeholders only). Start the mock Upstream and Aegis first.

  uv run --project backend python demo/agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

import httpx2
from openai import AsyncOpenAI

AEGIS_URL = os.getenv("AEGIS_URL", "http://127.0.0.1:8000").rstrip("/")
MODEL = os.getenv("AEGIS_MODEL", "gpt-5-mini")
SESSION = "demo-" + uuid.uuid4().hex[:8]
TASK = (
    "Transfer 75000 naira to Chinedu Okafor. Look up the customer first, "
    "then initiate the transfer."
)

CUSTOMERS: list[dict[str, Any]] = [
    {
        "name": "Chinedu Okafor",
        "bvn": "22334455667",
        "nin": "18938412256",
        "phone": "0803 123 4567",
        "account_no": "0123456789",
        "email": "chinedu.okafor@example.ng",
    },
    {
        "name": "Ada Obi",
        "bvn": "18938412234",
        "nin": "18938412257",
        "phone": "0805 442 1189",
        "account_no": "2032149875",
        "email": "ada.obi@example.ng",
    },
    {
        "name": "Ngozi Eze",
        "bvn": "22110987654",
        "nin": "22110987655",
        "phone": "0705 442 1189",
        "account_no": "3114327650",
        "email": "ngozi.eze@example.ng",
    },
    {
        "name": "Musa Danjuma",
        "bvn": "22334455678",
        "nin": "22334455679",
        "phone": "0809 234 1187",
        "account_no": "0176543210",
        "email": "musa.danjuma@example.ng",
    },
    {
        "name": "Titi Adeyemi",
        "bvn": "11987654321",
        "nin": "11987654322",
        "phone": "0816 552 3112",
        "account_no": "0765432109",
        "email": "titi.a@example.ng",
    },
]

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up a bank customer by full name.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_transfer",
            "description": "Send naira from a customer account to another account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_no": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["account_no", "amount"],
            },
        },
    },
]


def lookup_customer(name: str) -> dict[str, Any]:
    """Tool 1: the real record, including BVN/NIN/phone/account."""
    for customer in CUSTOMERS:
        if customer["name"].lower() == name.lower():
            return dict(customer)
    return {"error": f"No customer named {name}."}


def initiate_transfer(account_no: str, amount: float) -> dict[str, Any]:
    """Tool 2: pretend to move money, echoing the account and recipient."""
    for customer in CUSTOMERS:
        if customer["account_no"] == account_no:
            return {
                "status": "completed",
                "reference": "TRF-" + uuid.uuid4().hex[:10].upper(),
                "account_no": account_no,
                "amount": amount,
                "recipient": customer["name"],
            }
    return {"error": f"No account {account_no}."}


def execute_tool(name: str, arguments: str) -> dict[str, Any]:
    """Execute one Upstream tool call; arguments are already reinjected."""
    args = json.loads(arguments or "{}")
    if name == "lookup_customer":
        return lookup_customer(str(args.get("name", "")))
    if name == "initiate_transfer":
        return initiate_transfer(str(args.get("account_no", "")), float(args.get("amount", 0)))
    return {"error": f"Unknown tool {name}."}


def _message_lines(message: dict[str, Any]) -> list[str]:
    """One transcript message as readable lines (no truncation of values)."""
    role = message.get("role", "?")
    lines: list[str] = []
    content = message.get("content")
    if content:
        lines.append(f"{role}: {content}")
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        lines.append(
            f"assistant -> {function.get('name')}({function.get('arguments', '{}')})"
        )
    if not lines:
        lines.append(f"{role}: (empty)")
    return lines


def _panel(title: str, lines: list[str]) -> None:
    print(f"\n{'=' * 30} {title} {'=' * 30}")
    for line in lines:
        print(line)
    print("=" * (len(title) + 62))


def _wiretap_lines(body: dict[str, Any]) -> list[str]:
    lines = [f"model={body.get('model')} stream={body.get('stream')}"]
    for message in body.get("messages", []):
        lines.extend(_message_lines(message))
    return lines


async def main() -> None:
    async with httpx2.AsyncClient(trust_env=False, timeout=60.0) as http:
        try:
            (await http.get(f"{AEGIS_URL}/healthz")).raise_for_status()
        except httpx2.HTTPError:
            raise SystemExit(
                "Aegis is not running. Start it first:\n"
                "  cd backend && uv run uvicorn app.main:app --port 8000\n"
                "and the mock Upstream:\n"
                "  cd backend && uv run python scripts/mock_upstream.py"
            ) from None

        client = AsyncOpenAI(
            base_url=f"{AEGIS_URL}/v1",
            api_key=os.getenv("OPENAI_API_KEY", "sk-aegis-demo-not-validated"),
            default_headers={"X-Aegis-Session": SESSION},
            http_client=httpx2.AsyncClient(trust_env=False),
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": TASK}]
        request_ids: list[str] = []

        print(f"Aegis: {AEGIS_URL}  session: {SESSION}")
        print(f"Task: {TASK}")
        for _ in range(8):
            raw = await client.chat.completions.with_raw_response.create(
                model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
            )
            request_ids.append(raw.headers.get("x-aegis-request-id", ""))
            completion = raw.parse()
            message = completion.choices[0].message
            tool_calls = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in (message.tool_calls or [])
            ]
            assistant = {
                "role": "assistant",
                "content": message.content or "",
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
            messages.append(assistant)
            if not tool_calls:
                break
            for call in tool_calls:
                result = execute_tool(
                    call["function"]["name"], call["function"]["arguments"]
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result),
                    }
                )
        await client.close()

        request_id = next((rid for rid in reversed(request_ids) if rid), "")
        tap = await http.get(f"{AEGIS_URL}/v1/aegis/wiretap/{request_id}")
        tap.raise_for_status()

    _panel("AGENT SAW", [line for message in messages for line in _message_lines(message)])
    _panel(
        "UPSTREAM SAW",
        [f"Wire Tap {request_id}"] + _wiretap_lines(tap.json()),
    )


if __name__ == "__main__":
    asyncio.run(main())
