"""Shared helpers for the collectors, scorers and drafters."""

import hashlib
import json
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


async def launch_chromium(pw, **kwargs):
    """Launch Chromium, falling back to the installed Google Chrome.

    The bundled Playwright browser can't be downloaded from some networks
    (cdn.playwright.dev is blocked), so we use the system Chrome via
    channel="chrome" when the bundled binary is absent. Override with
    PLAYWRIGHT_CHANNEL (e.g. "chrome", "msedge", or "" to force bundled).
    """
    channel = os.getenv("PLAYWRIGHT_CHANNEL")
    if channel is None:
        exe = pw.chromium.executable_path
        channel = None if (exe and Path(exe).exists()) else "chrome"
    if channel:
        kwargs["channel"] = channel
    return await pw.chromium.launch(**kwargs)


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def load_profile() -> str:
    """profile.md without TODO lines — they must never reach the LLM."""
    path = ROOT / "profile.md"
    if not path.exists():
        path = ROOT / "profile.example.md"   # fresh clone: copy it to profile.md and edit
    lines = path.read_text().splitlines()
    return "\n".join(ln for ln in lines if "TODO" not in ln)


def load_style_notes() -> str:
    p = ROOT / "style_notes.md"
    return p.read_text() if p.exists() else ""


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().rstrip("/").lower().encode()).hexdigest()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<(script|style).*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_json(text: str) -> dict:
    """Extract the first JSON object from an LLM reply (tolerates code fences)."""
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError(f"no JSON object in LLM reply: {text[:200]!r}")
    return json.loads(m.group(0))


def keyword_hits(text: str, cfg: dict) -> int:
    t = text.lower()
    kws = cfg["keywords"]["primary"] + cfg["keywords"]["secondary"]
    return sum(1 for k in kws if k.lower() in t)
