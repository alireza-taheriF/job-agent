"""
Karlancer inbox monitor: finds new messages and records them in inbox_messages.
Never auto-replies. UNVERIFIED selectors — see collector.py note.
"""

from datetime import datetime

from agents.common import launch_chromium
from agents.karlancer.collector import SESSION_FILE, SessionError
from db.models import InboxMessage

INBOX_URL = "https://www.karlancer.com/messages"


async def check_inbox(db) -> list[InboxMessage]:
    if not SESSION_FILE.exists():
        raise SessionError("no Karlancer session")
    from playwright.async_api import async_playwright
    new = []
    async with async_playwright() as pw:
        browser = await launch_chromium(pw, headless=True)
        try:
            ctx = await browser.new_context(storage_state=str(SESSION_FILE))
            page = await ctx.new_page()
            await page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=45000)
            if "/login" in page.url:
                raise SessionError("Karlancer session expired")
            items = await page.eval_on_selector_all(
                "a[href*='/message'], a[href*='/conversation']",
                "els => els.map(e => [e.href, e.innerText.trim()])")
        finally:
            await browser.close()
    for href, text in items:
        if not text or db.query(InboxMessage).filter_by(subject=href).first():
            continue
        m = InboxMessage(source="karlancer", sender="karlancer", subject=href,
                         content=text[:2000], received_at=datetime.utcnow(),
                         notified_at=datetime.utcnow())
        db.add(m)
        new.append(m)
    db.commit()
    return new
