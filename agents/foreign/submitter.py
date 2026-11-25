"""
Submit an approved foreign application.

If the posting gives an application email address, the cover letter (plus
data/CV.pdf when present) is emailed after the user pressed ✅ Apply.
Otherwise the job is an ATS form: the bot returns the link and the letter for
Ali to paste — forms are never auto-filled (no CAPTCHA bypass, no ToS risk).
"""

import json
import re

from agents.common import ROOT, load_config
from messaging import mailer

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
APPLY_HINT = re.compile(r"(apply|application|send (your )?(cv|resume)|email (us|your))", re.I)
SKIP_LOCAL = ("noreply", "no-reply", "privacy", "gdpr", "support", "abuse", "legal")


def application_email(description: str) -> str | None:
    """Best guess at the address the posting asks applicants to write to."""
    text = description or ""
    best = None
    for m in EMAIL.finditer(text):
        addr = m.group(0).rstrip(".")
        if any(k in addr.lower() for k in SKIP_LOCAL):
            continue
        window = text[max(0, m.start() - 160): m.start()]
        if APPLY_HINT.search(window):
            return addr
        best = best or addr
    return best


def cv_attachments() -> list:
    for name in ("CV.pdf", "cv.pdf", "Resume.pdf"):
        p = ROOT / "data" / name
        if p.exists():
            return [p]
    return []


def submit_application(job, proposal) -> tuple[str, str]:
    """Return (status, note). status ∈ sent | dry_run | manual."""
    try:
        letter = json.loads(proposal.content).get("cover_letter", "") if proposal else ""
    except ValueError:
        letter = proposal.content if proposal else ""
    to = application_email(job.description or "")
    if not to:
        return "manual", "no application email in the posting — apply via the link"
    cfg = load_config()["application"]
    subject = f"Application: {job.title}" + (f" — {job.company}" if job.company else "")
    status, note = mailer.send(to, subject, letter, approved=True,
                               dry_run=cfg.get("dry_run", True), attachments=cv_attachments())
    return status, note
