"""Official OpenAI SDK smoke test (PRD 12.2): base_url = Aegis, normal + stream=True.

Start the two servers first, then run this script:

  uv run python scripts/mock_upstream.py            # mock Upstream on :9000
  uv run uvicorn app.main:app --port 8000           # Aegis on :8000
  uv run python scripts/sdk_smoke.py
"""

import httpx
import httpx2  # The OpenAI SDK v3 transport; `trust_env=False` skips the dev box's system proxy.
from openai import AsyncOpenAI

AEGIS_BASE_URL = "http://127.0.0.1:8000/v1"


async def main() -> None:
    async with httpx.AsyncClient(trust_env=False) as preflight:
        try:
            (await preflight.get("http://127.0.0.1:8000/healthz")).raise_for_status()
            (await preflight.get("http://127.0.0.1:9000/_tap")).raise_for_status()
        except httpx.HTTPError:
            raise SystemExit(
                "Start both servers first:\n"
                "  uv run python scripts/mock_upstream.py\n"
                "  uv run uvicorn app.main:app --port 8000"
            ) from None

    client = AsyncOpenAI(
        base_url=AEGIS_BASE_URL,
        api_key="sk-smoke-not-validated",
        http_client=httpx2.AsyncClient(trust_env=False),
    )

    completion = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "Say one sentence about Lagos."}],
    )
    print("non-stream:", completion.choices[0].message.content)

    stream = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "Say one sentence about Lagos, streamed."}],
        stream=True,
    )
    parts: list[str] = []
    finish_reason = None
    async for chunk in stream:
        if chunk.choices:
            if chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
            finish_reason = chunk.choices[0].finish_reason or finish_reason
    print("streamed:", "".join(parts), f"(finish_reason={finish_reason})")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
