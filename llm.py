"""
LLM abstraction layer with two backends, caching, and rate limiting.

Backends
--------
claude_cli (default)
    Calls the installed `claude` CLI in headless print mode (`claude -p ...`).
    Requires a live Claude Code session — authenticate once by running `claude`
    interactively, or on a VPS via `claude setup-token`.

anthropic_api
    Direct Anthropic API call. Requires ANTHROPIC_API_KEY in .env and
    LLM_BACKEND=anthropic_api.

All responses are cached in SQLite by SHA-256(backend+prompt).
Nothing is scored twice unless skip_cache=True.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
from typing import Optional

import log as _log_mod

log = _log_mod.get_logger("llm")

# Module-level state (initialized lazily so the event loop exists first)
_semaphore: Optional[asyncio.Semaphore] = None
_minute_calls: list[float] = []


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENT", "2")))
    return _semaphore


def _prompt_hash(prompt: str, backend: str) -> str:
    return hashlib.sha256(f"{backend}:{prompt}".encode()).hexdigest()


async def _rate_limit() -> None:
    global _minute_calls
    max_per_min = int(os.getenv("LLM_MAX_PER_MINUTE", "8"))
    now = time.monotonic()
    _minute_calls = [t for t in _minute_calls if now - t < 60.0]
    if len(_minute_calls) >= max_per_min:
        wait = 61.0 - (now - _minute_calls[0])
        if wait > 0:
            log.info("llm.rate_limit", wait_seconds=round(wait, 1))
            await asyncio.sleep(wait)
    _minute_calls.append(time.monotonic())


async def _call_claude_cli(prompt: str) -> str:
    timeout = int(os.getenv("LLM_TIMEOUT", "90"))
    exe = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    cmd = [exe, "-p", prompt, "--output-format", "json"]
    model = os.getenv("CLAUDE_MODEL", "").strip()
    if model:
        cmd += ["--model", model]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=tempfile.gettempdir(),  # neutral dir: don't load project/user CLAUDE.md context
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"claude CLI timed out after {timeout}s")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"claude CLI exited {proc.returncode}: {err[:400]}")

    raw = stdout.decode(errors="replace").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if data.get("is_error"):
                raise RuntimeError(f"claude CLI reported error: {data}")
            return data.get("result", raw)
    except json.JSONDecodeError:
        pass
    return raw


async def _call_anthropic_api(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (needed for anthropic_api backend)")
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed: pip install anthropic")

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6").strip()
    client = anthropic.AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


async def call_llm(
    prompt: str,
    db_session=None,
    cache_key: Optional[str] = None,
    skip_cache: bool = False,
) -> str:
    """
    Send a prompt to the configured backend with caching and rate limiting.

    Args:
        prompt:      Self-contained, stateless prompt.
        db_session:  SQLAlchemy session for cache reads/writes. None = no caching.
        cache_key:   Override the default cache key (SHA-256 of backend+prompt).
        skip_cache:  Force a fresh LLM call even if a cached response exists.

    Returns:
        The model's text response as a plain string.
    """
    from db.models import LLMCache

    backend = os.getenv("LLM_BACKEND", "claude_cli").strip()
    key = cache_key or _prompt_hash(prompt, backend)

    if db_session is not None and not skip_cache:
        cached = db_session.query(LLMCache).filter_by(prompt_hash=key).first()
        if cached:
            log.debug("llm.cache_hit", key=key[:8], backend=backend)
            return cached.response

    async with _get_semaphore():
        await _rate_limit()
        log.info("llm.call", backend=backend, prompt_chars=len(prompt))

        if backend == "claude_cli":
            response = await _call_claude_cli(prompt)
        elif backend == "anthropic_api":
            response = await _call_anthropic_api(prompt)
        else:
            raise ValueError(f"Unknown LLM_BACKEND='{backend}'. Use 'claude_cli' or 'anthropic_api'.")

    if db_session is not None:
        entry = LLMCache(prompt_hash=key, backend=backend, response=response)
        db_session.merge(entry)
        db_session.commit()

    return response


async def health_check() -> dict:
    """
    Verify the LLM backend is reachable.
    Returns {"ok": True, "backend": "..."} or {"ok": False, "error": "..."}.
    Called at startup and on a scheduled heartbeat.
    """
    backend = os.getenv("LLM_BACKEND", "claude_cli")
    try:
        resp = await call_llm("Reply with exactly the word: OK", db_session=None, skip_cache=True)
        return {"ok": "ok" in resp.strip().lower(), "backend": backend, "sample": resp[:60]}
    except Exception as exc:
        return {"ok": False, "backend": backend, "error": str(exc)}
