"""
APScheduler wiring (Asia/Tehran).

Jobs: foreign collection, Karlancer collection, daily summary, LLM health check.
Each job catches its own exceptions, logs, and alerts on Telegram — one failing
job never brings down the scheduler. /pause sets bot_data["paused"].
"""

import os

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import log as _log_mod
import llm
from bot.digest import send_digest

log = _log_mod.get_logger("scheduler")


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def _chat() -> int:
    return int(os.environ["TELEGRAM_USER_ID"])


async def _alert(app, text: str):
    try:
        await app.bot.send_message(_chat(), text)
    except Exception as exc:
        log.error("scheduler.alert_failed", error=str(exc)[:200])


def _paused(app) -> bool:
    return bool(app.bot_data.get("paused"))


async def job_foreign(app):
    if _paused(app):
        return
    try:
        from pipeline import run_foreign
        s = await run_foreign()
        await _alert(app, f"🌍 Foreign: collected {s['collected']}, new {s['new']}, shortlisted {s['shortlisted']}")
        if s["shortlisted"]:
            await send_digest(app.bot, _chat(), only_new_hours=2)
    except Exception as exc:
        log.exception("scheduler.foreign_failed")
        await _alert(app, f"⚠️ Foreign collection failed: {str(exc)[:300]}")


async def job_karlancer(app):
    if _paused(app):
        return
    try:
        from agents.karlancer.collector import SessionError
        from pipeline import run_karlancer
        try:
            s = await run_karlancer()
        except SessionError as exc:
            await _alert(app, f"🟠 Karlancer stopped: {exc}")
            return
        await _alert(app, f"🟠 Karlancer: collected {s['collected']}, new {s['new']}, shortlisted {s['shortlisted']}")
        if s["shortlisted"]:
            await send_digest(app.bot, _chat(), only_new_hours=2)
    except Exception as exc:
        log.exception("scheduler.karlancer_failed")
        await _alert(app, f"⚠️ Karlancer collection failed: {str(exc)[:300]}")


async def job_inbox(app):
    if _paused(app):
        return
    from agents.karlancer.collector import SessionError
    from agents.karlancer.inbox import check_inbox
    from db.session import session_scope
    try:
        with session_scope() as db:
            new = await check_inbox(db)
            texts = [m.content[:200] for m in new]
        for t in texts:
            await _alert(app, f"📬 Karlancer inbox:\n{t}")
    except SessionError:
        pass  # already reported by the daily collection job
    except Exception as exc:
        log.exception("scheduler.inbox_failed")
        await _alert(app, f"⚠️ Inbox check failed: {str(exc)[:300]}")


async def job_style_notes(app):
    """Weekly: summarise Apply/Skip/Edit feedback into style_notes.md."""
    from agents.common import ROOT, parse_json
    from db.models import FeedbackEvent
    from db.session import session_scope
    from datetime import datetime, timedelta
    with session_scope() as db:
        edits = [f.edit_instruction for f in db.query(FeedbackEvent).filter(
            FeedbackEvent.action == "edit",
            FeedbackEvent.created_at >= datetime.utcnow() - timedelta(days=7)).all()]
    if len(edits) < 3:
        return
    try:
        reply = await llm.call_llm(
            "Summarise these user edit instructions for job proposals into at most 5 short "
            'style rules. JSON only: {"rules": ["..."]}\n' + "\n".join(edits))
        rules = parse_json(reply)["rules"]
        (ROOT / "style_notes.md").write_text(
            "# Style Notes\n\nAutomatically updated weekly from Edit feedback.\n"
            f"Last updated: {datetime.utcnow():%Y-%m-%d}\n\n## Rules\n"
            + "\n".join(f"- {r}" for r in rules) + "\n")
    except Exception:
        log.exception("scheduler.style_notes_failed")


async def job_outreach(app):
    """Daily: mark replies, draft follow-ups and new emails, send cards for approval."""
    if _paused(app):
        return
    from agents.outreach import cold_email
    from bot.outreach import send_outreach_cards
    from db.session import session_scope
    from messaging import mailer
    try:
        try:
            senders = mailer.senders_since(30)
        except Exception as exc:
            senders = set()
            log.warning("scheduler.imap_failed", error=str(exc)[:200])
        with session_scope() as db:
            replied = cold_email.mark_replies(db, senders)
            await cold_email.draft_followups(db)
        if replied:
            await _alert(app, f"🎉 {replied} outreach contact(s) replied — check your inbox.")
        await send_outreach_cards(app.bot, _chat())
    except Exception as exc:
        log.exception("scheduler.outreach_failed")
        await _alert(app, f"⚠️ Outreach job failed: {str(exc)[:300]}")


async def job_summary(app):
    if not _paused(app):
        await send_digest(app.bot, _chat())


async def job_health(app):
    res = await llm.health_check()
    if not res["ok"]:
        await _alert(app, f"⚠️ LLM health check failed: {res}")


def build_scheduler(app) -> AsyncIOScheduler:
    cfg = load_config()["schedule"]
    sched = AsyncIOScheduler(timezone="Asia/Tehran")
    hm = lambda s: dict(zip(("hour", "minute"), map(int, s.split(":"))))
    sched.add_job(job_foreign, "cron", args=[app], id="foreign", **hm(cfg["foreign_collect_time"]))
    sched.add_job(job_karlancer, "cron", args=[app], id="karlancer", **hm(cfg["karlancer_collect_time"]))
    sched.add_job(job_outreach, "cron", args=[app], id="outreach", **hm(cfg.get("outreach_time", "10:00")))
    sched.add_job(job_summary, "cron", args=[app], id="summary", **hm(cfg["daily_summary_time"]))
    sched.add_job(job_inbox, "interval", args=[app], id="inbox", minutes=cfg["inbox_check_interval_minutes"])
    sched.add_job(job_style_notes, "cron", args=[app], id="style_notes", day_of_week="sun", hour=22)
    sched.add_job(job_health, "interval", args=[app], id="health", minutes=60)
    log.info("scheduler.built", jobs=[j.id for j in sched.get_jobs()])
    return sched
