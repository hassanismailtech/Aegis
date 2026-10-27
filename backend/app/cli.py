"""`aegis doctor`: check Redis, the NER model and Upstream; print versions."""

from __future__ import annotations

import argparse
import asyncio
import platform
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from urllib.parse import urlsplit

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

CHECK_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def _safe_url(url: str) -> str:
    """Scheme, host, port and path only: never print URL credentials."""
    parsed = urlsplit(url)
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    if parsed.scheme:
        return f"{parsed.scheme}://{host}{port}{path}"
    return f"{host}{port}{path}"


def _versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "aegis": _version("aegis"),
        "fastapi": _version("fastapi"),
        "pydantic": _version("pydantic"),
        "redis": _version("redis"),
        "httpx": _version("httpx"),
        "torch": _version("torch"),
        "transformers": _version("transformers"),
        "gliner": _version("gliner"),
    }


async def check_redis() -> Check:
    try:
        client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=CHECK_TIMEOUT_SECONDS,
            socket_timeout=CHECK_TIMEOUT_SECONDS,
        )
    except ValueError:
        return Check("redis", False, f"{_safe_url(settings.redis_url)} invalid URL")
    try:
        await client.ping()
        try:
            info = await client.info("server")
            server = str(info.get("redis_version", "unknown"))
        except RedisError:
            server = "unknown"
        return Check("redis", True, f"{_safe_url(settings.redis_url)} (Redis {server})")
    except (RedisError, OSError, asyncio.TimeoutError):
        return Check("redis", False, f"{_safe_url(settings.redis_url)} unreachable")
    finally:
        await client.aclose()


def check_model() -> Check:
    if not settings.ner_enabled:
        return Check("model", True, f"{settings.ner_model} (NER disabled)")
    from app.scrubber.ner import get_ner

    ner = get_ner()
    try:
        if not ner.ready:
            ner.warm()
    except Exception:  # noqa: BLE001 — report only the model name, never inputs
        return Check("model", False, f"{settings.ner_model} failed to load")
    return Check("model", True, f"{settings.ner_model} warm (threshold {settings.ner_threshold})")


async def check_upstream() -> Check:
    url = settings.upstream_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=CHECK_TIMEOUT_SECONDS,
            trust_env=False,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
        return Check(
            "upstream",
            True,
            f"{_safe_url(url)} reachable (HTTP {response.status_code})",
        )
    except (httpx.HTTPError, OSError):
        return Check("upstream", False, f"{_safe_url(url)} unreachable")


async def _run_checks() -> list[Check]:
    redis_check, upstream_check = await asyncio.gather(check_redis(), check_upstream())
    model_check = await asyncio.to_thread(check_model)
    return [redis_check, model_check, upstream_check]


def _print_report(checks: list[Check]) -> None:
    print("Aegis doctor")
    for name, value in _versions().items():
        print(f"  {name:<12} {value}")
    print()
    for check in checks:
        status = "ok" if check.ok else "FAIL"
        print(f"  {check.name:<12} {status:<4} {check.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check Redis, the NER model and Upstream")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print("Checking Redis, NER model and Upstream ...", file=sys.stderr)
        checks = asyncio.run(_run_checks())
        _print_report(checks)
        return 0 if all(check.ok for check in checks) else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
