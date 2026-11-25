"""
Karlancer project collector.

Uses the Playwright session saved by `python login_helper.py karlancer`
(data/sessions/karlancer.json). If the session is missing or expired it raises
SessionError so the caller can alert on Telegram — it never tries to log in or
bypass a CAPTCHA.

UNVERIFIED: the listing URL and link pattern below were written without access
to a logged-in page; adjust LIST_URL / LINK_RE if collection returns nothing.
"""

import json
import random
import re
from pathlib import Path

import log as _log_mod
from agents.common import ROOT, launch_chromium, load_config, strip_html, url_hash

log = _log_mod.get_logger("karlancer.collector")

SESSION_FILE = ROOT / "data" / "sessions" / "karlancer.json"
LIST_URL = "https://www.karlancer.com/search"  # verified 2026-10-10 via the site nav link


class SessionError(RuntimeError):
    pass


def _fa_digits(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٬،", "0123456789,,"))


async def collect_projects(limit: int = 50) -> list[dict]:
    """Reading the listing is public (verified 2026-10-10); a session is used if present."""
    from urllib.parse import quote
    from playwright.async_api import async_playwright

    cfg = load_config()
    rl = cfg["rate_limits"]["karlancer"]
    terms = ["python", "django", "fastapi", "llm", "هوش مصنوعی", "یادگیری ماشین", "ocr", "پردازش تصویر", "ربات"]
    found: dict[str, str] = {}
    out = []
    async with async_playwright() as pw:
        browser = await launch_chromium(pw, headless=True)
        kw = {"storage_state": str(SESSION_FILE)} if SESSION_FILE.exists() else {}
        ctx = await browser.new_context(**kw)
        page = await ctx.new_page()
        try:
            for term in terms:
                await page.goto(f"{LIST_URL}?q={quote(term)}", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2000)
                links = await page.eval_on_selector_all(
                    "a[href*='/projects/']", "els => els.map(e => [e.href, e.innerText.trim()])")
                if not links and "captcha" in (await page.content()).lower():
                    raise SessionError("Karlancer showed a CAPTCHA — stopped")
                for href, text in links:
                    found.setdefault(href.split("?")[0], text.split("\n")[0])
            for url, title in list(found.items())[:limit]:
                await page.wait_for_timeout(1000 * random.uniform(rl["min_delay_seconds"], rl["max_delay_seconds"]))
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                main = page.locator("main").first
                body = await (main if await main.count() else page.locator("body")).inner_text()
                name = (await page.title()).split("|")[0].strip() or title
                core = name.replace("پروژه", "", 1).strip()[:25]
                i = body.rfind(core) if core else -1
                if i > 0:
                    body = body[i:]  # drop the site navigation before the project title
                out.append({
                    "source": "karlancer", "url": url, "url_hash": url_hash(url),
                    "title": (await page.title()).split("|")[0].strip() or title,
                    "description": body[:5000], "skills_json": json.dumps([]),
                    "budget_raw": None, "currency": "IRT", "is_remote": True,
                })
        finally:
            await browser.close()
    return out
