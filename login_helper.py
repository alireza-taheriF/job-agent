"""
Headed browser login helper.

Opens a real Chromium window so you can log in manually.
After login, press Enter — the session (cookies + localStorage) is saved
to data/sessions/<site>.json and reused by the agents.

Usage:
    python login_helper.py karlancer
    python login_helper.py linkedin
    python login_helper.py gmail
    python login_helper.py karlancer --chrome   # use real Chrome (best for Google sign-in)
    python login_helper.py list       # show saved sessions

Sessions are gitignored and never printed to logs.
"""

import asyncio
import json
import pathlib
import sys

import log as _log_mod
from dotenv import load_dotenv

load_dotenv()
_log_mod.configure()
log = _log_mod.get_logger("login_helper")

SESSIONS_DIR = pathlib.Path("data/sessions")

SITES = {
    "karlancer": {
        "url": "https://karlancer.com/login",
        "label": "کارلنسر",
        "check_url": "https://karlancer.com/dashboard",
    },
    "linkedin": {
        "url": "https://www.linkedin.com/login",
        "label": "LinkedIn",
        "check_url": "https://www.linkedin.com/feed/",
    },
    "gmail": {
        "url": "https://mail.google.com",
        "label": "Gmail",
        "check_url": "https://mail.google.com/mail/u/0/",
    },
}


async def do_login(site: str) -> None:
    from playwright.async_api import async_playwright

    if site not in SITES:
        print(f"Unknown site: '{site}'. Available: {', '.join(SITES)}")
        sys.exit(1)

    info = SITES[site]
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_path = SESSIONS_DIR / f"{site}.json"
    profile_dir = SESSIONS_DIR / f"{site}_profile"

    print(f"\n{'='*55}")
    print(f"  Login helper — {info['label']}")
    print(f"  Session will be saved to: {session_path}")
    print(f"{'='*55}\n")
    print("  A browser window will open.")
    print("  Log in manually, then come back here and press Enter.\n")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            channel="chrome",  # real Chrome: Google rejects sign-in from bundled Chromium
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800},
            locale="fa-IR",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(info["url"])
        log.info("login_helper.browser_opened", site=site, url=info["url"])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: input("  Press Enter when done logging in…"))

        state = await context.storage_state()
        session_path.write_text(json.dumps(state))
        cookies_count = len(state.get("cookies", []))
        log.info("login_helper.session_saved", site=site, cookies=cookies_count)
        print(f"\n  ✅ Session saved ({cookies_count} cookies) → {session_path}\n")

        await context.close()


async def do_login_chrome(site: str) -> None:
    """Open the real Chrome app (no automation flags), let the user log in, then
    attach over CDP and save the session. Google accepts sign-in this way."""
    import subprocess
    import time
    from playwright.async_api import async_playwright

    info = SITES[site]
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    profile = (SESSIONS_DIR / "chrome_profile").resolve()
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    print("\n  Quit any running Chrome windows of THIS profile first (a separate profile is used).")
    proc = subprocess.Popen([chrome, f"--user-data-dir={profile}", "--remote-debugging-port=9223",
                             "--no-first-run", info["url"]])
    time.sleep(4)
    print(f"  Log in to {info['label']} in the Chrome window, then press Enter here.\n")
    await asyncio.get_event_loop().run_in_executor(None, lambda: input("  Press Enter when done…"))
    # Close Chrome first, then read the saved profile: CDP storage_state misses
    # localStorage tokens (Karlancer keeps its auth-token there).
    proc.terminate()
    proc.wait(timeout=15)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(profile), channel="chrome", headless=True)
        page = await ctx.new_page()
        await page.goto(info.get("check_url", info["url"]), wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        state = await ctx.storage_state()
        await ctx.close()
    has_token = any(i["name"] == "auth-token" for o in state.get("origins", []) for i in o["localStorage"])
    if site == "karlancer" and not has_token:
        print("\n  ❌ Not logged in to Karlancer (no auth-token). Session NOT saved — try again.\n")
        return
    path = SESSIONS_DIR / f"{site}.json"
    path.write_text(json.dumps(state))
    path.chmod(0o600)
    print(f"\n  ✅ Session saved ({len(state.get('cookies', []))} cookies)\n")
    return



async def check_session(site: str) -> bool:
    path = SESSIONS_DIR / f"{site}.json"
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text())
        return len(state.get("cookies", [])) > 0
    except Exception:
        return False


async def list_sessions() -> None:
    print("\nSaved sessions:")
    for site in SITES:
        ok = await check_session(site)
        mark = "✅" if ok else "❌"
        print(f"  {mark}  {site:<12} ({SESSIONS_DIR / (site + '.json')})")
    print()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not arg or arg == "list":
        asyncio.run(list_sessions())
        if not arg:
            print(f"Usage: python login_helper.py <site>")
            print(f"Sites: {', '.join(SITES)}")
    elif len(sys.argv) > 2 and sys.argv[2] == "--chrome":
        asyncio.run(do_login_chrome(arg))
    else:
        asyncio.run(do_login(arg))
