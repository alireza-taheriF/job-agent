"""
Cold outreach to hiring managers / engineers, one person at a time.

Flow: contacts CSV → personalised draft (LLM, profile facts only) → Telegram
card → ✅ Send → SMTP. One follow-up after `cold_email.follow_up_after_days`
if nobody replied. Daily cap `cold_email.max_per_day`. Every send needs an
explicit tap; auto_send.cold_emails stays OFF unless Ali changes it.

CSV columns (header row required): company,name,role,email,linkedin,note
Rows without an email are skipped (LinkedIn-only contacts are messaged by hand).
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import log as _log_mod
from agents.common import load_config, load_profile, load_style_notes, parse_json
from db.models import ColdEmailTarget
from llm import call_llm
from messaging import mailer

log = _log_mod.get_logger("outreach")


def import_contacts(db, path: Path) -> dict:
    added = skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            addr = (row.get("email") or "").strip().lower()
            if "@" not in addr:
                skipped += 1
                continue
            if db.query(ColdEmailTarget).filter_by(contact_email=addr).first():
                skipped += 1
                continue
            db.add(ColdEmailTarget(
                company=row.get("company"), contact_name=row.get("name"),
                contact_role=row.get("role"), contact_email=addr,
                source_url=row.get("linkedin"), note=row.get("note"), status="new"))
            added += 1
    db.flush()
    return {"added": added, "skipped": skipped}


def sent_today(db) -> int:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(ColdEmailTarget).filter(ColdEmailTarget.sent_at >= start).count()


def remaining_today(db) -> int:
    return max(0, load_config()["cold_email"]["max_per_day"] - sent_today(db))


async def draft(db, t: ColdEmailTarget, follow_up: bool = False) -> ColdEmailTarget:
    kind = ("a SHORT follow-up (60-90 words) to the email below, which got no reply. "
            "Polite, no guilt, one new concrete detail, easy to say no.\n\nPREVIOUS EMAIL:\n"
            f"{t.email_draft}" if follow_up else
            "a first cold email (110-160 words)")
    prompt = f"""Write {kind} from the candidate to {t.contact_name or 'the hiring team'} ({t.contact_role or 'UNKNOWN role'}) at {t.company or 'UNKNOWN company'}.
Goal: ask whether their AI/ML team is hiring and whether a 15-minute call or a referral is possible. Open to fully remote or relocation with visa sponsorship.
HARD RULES: use ONLY facts in the profile. Never invent experience, metrics, employers, degrees, papers or patents. No flattery clichés. Plain text, no markdown. Sign as "Alireza Taheri".
Personal hook from Ali (use it if present, do not exaggerate it): {t.note or 'none'}

PROFILE:
{load_profile()}

STYLE NOTES:
{load_style_notes()}

Reply with ONLY JSON: {{"subject": "<max 8 words>", "body": "<email body>"}}"""
    data = parse_json(await call_llm(prompt, db, skip_cache=True))
    t.subject = ("Re: " + (t.subject or "")) if follow_up else data["subject"]
    t.email_draft = data["body"]
    t.status = "followup_draft" if follow_up else "draft"
    return t


async def draft_new(db, n: int) -> int:
    made = 0
    for t in db.query(ColdEmailTarget).filter_by(status="new").limit(n).all():
        try:
            await draft(db, t)
            made += 1
        except Exception as exc:
            log.warning("outreach.draft_failed", to=t.contact_email, error=str(exc)[:200])
        db.flush()
    return made


async def draft_followups(db) -> int:
    cfg = load_config()["cold_email"]
    due = (db.query(ColdEmailTarget)
           .filter(ColdEmailTarget.status == "sent", ColdEmailTarget.reply_received.is_(False),
                   ColdEmailTarget.follow_up_at <= datetime.utcnow(),
                   ColdEmailTarget.follow_ups < cfg.get("max_follow_ups", 1)).all())
    for t in due:
        await draft(db, t, follow_up=True)
    return len(due)


def send(db, t: ColdEmailTarget, approved: bool) -> tuple[str, str]:
    if t.opted_out or t.status in ("replied", "opted_out"):
        return "skipped", "contact replied or opted out"
    if remaining_today(db) <= 0:
        return "capped", "daily cold-email limit reached — try tomorrow"
    dry = load_config()["application"].get("dry_run", True)
    status, note = mailer.send(t.contact_email, t.subject or "Quick question", t.email_draft,
                               approved=approved, dry_run=dry)
    if status == "sent":
        if t.status == "followup_draft":
            t.follow_ups = (t.follow_ups or 0) + 1
        t.status, t.sent_at = "sent", datetime.utcnow()
        t.follow_up_at = t.sent_at + timedelta(days=load_config()["cold_email"]["follow_up_after_days"])
    return status, note


def mark_replies(db, senders: set[str]) -> int:
    n = 0
    for t in db.query(ColdEmailTarget).filter(ColdEmailTarget.status.in_(("sent", "followup_draft"))).all():
        if t.contact_email in senders:
            t.reply_received, t.status = True, "replied"
            n += 1
    return n
