"""
Karlancer proposal submitter — runs ONLY after the user taps ✅ in Telegram.

Safety: gated by config application.karlancer_submit (default false) and
application.dry_run. In dry-run the form is filled but never submitted.
Stops (raises) on session expiry, CAPTCHA, or any missing form element.

VERIFIED 2026-10-10 (read-only): the project page opens a modal after
'ثبت پیشنهاد روی پروژه' ('ادامه و ثبت پیشنهاد') and the site also sells paid
proposal packs, so this single-textarea flow is INCOMPLETE — keep
karlancer_submit false until the multi-step flow is mapped.
Original note: selectors were written without access to a logged-in Karlancer
page. Test with dry_run: true first and adjust TEXTAREA / SUBMIT.
"""

from agents.common import ROOT, launch_chromium, load_config
from agents.karlancer.collector import SESSION_FILE, SessionError

TEXTAREA = "textarea"
SUBMIT = "button[type=submit]:has-text('ارسال')"


async def submit_proposal(url: str, text: str) -> tuple[str, str]:
    """Return (status, note): status in {'sent', 'dry_run', 'disabled'}."""
    cfg = load_config()["application"]
    if not cfg.get("karlancer_submit"):
        return "disabled", "karlancer_submit is false in config.yaml"
    if not SESSION_FILE.exists():
        raise SessionError("no Karlancer session — run: python login_helper.py karlancer")
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await launch_chromium(pw, headless=True)
        try:
            ctx = await browser.new_context(storage_state=str(SESSION_FILE))
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if "captcha" in (await page.content()).lower() or "/login" in page.url:
                raise SessionError("Karlancer session expired or CAPTCHA shown — stopped")
            box = page.locator(TEXTAREA).first
            if not await box.count():
                raise RuntimeError("proposal textarea not found (selectors need updating)")
            await box.fill(text)
            if cfg.get("dry_run"):
                return "dry_run", "form filled, not submitted (dry_run)"
            btn = page.locator(SUBMIT).first
            if not await btn.count():
                raise RuntimeError("submit button not found (selectors need updating)")
            await btn.click()
            await page.wait_for_timeout(3000)
            return "sent", (await page.title())[:200]
        finally:
            await browser.close()
