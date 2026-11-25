"""Message formatters for job cards sent via Telegram (DB-backed)."""

import json
from html import escape as e


def _skills(job) -> str:
    try:
        return ", ".join(json.loads(job.skills_json or "[]")[:8])
    except ValueError:
        return ""


def karlancer_card(job, proposal) -> str:
    return (
        f"📋 <b>{e(job.title)}</b>\n"
        f"💰 بودجه: {e(job.budget_raw or 'UNKNOWN')}\n"
        f"🏷 مهارت‌ها: {e(_skills(job)) or '—'}\n"
        f"⭐ امتیاز: <b>{job.fit_score:.0f}/100</b>\n"
        f"💬 {e(job.score_reason or '')}\n"
        f"🔗 <a href=\"{e(job.url)}\">مشاهده پروژه</a>\n\n"
        f"📝 <b>پیشنهاد پیش‌نویس:</b>\n"
        f"<blockquote>{e(proposal.content if proposal else '—')}</blockquote>"
    )


def foreign_card(job, proposal) -> str:
    letter = ""
    if proposal:
        try:
            letter = json.loads(proposal.content).get("cover_letter", "")
        except ValueError:
            letter = proposal.content
    return (
        f"🌍 <b>{e(job.title)}</b>\n"
        f"🏢 {e(job.company or 'UNKNOWN')}  ·  {e(job.location_note or 'remote')}\n"
        f"💰 {e(job.budget_raw or 'UNKNOWN')}\n"
        f"⭐ Fit: <b>{job.fit_score:.0f}/100</b>  ({e(job.source)})\n"
        f"💬 {e(job.score_reason or '')}\n"
        f"🔗 <a href=\"{e(job.url)}\">View job</a>\n\n"
        f"📄 <b>Cover letter draft:</b>\n"
        f"<blockquote>{e(letter[:2500])}</blockquote>"
    )


def outreach_card(t) -> str:
    kind = "Follow-up" if t.status == "followup_draft" else "Cold email"
    return (
        f"✉️ <b>{kind}</b> → {e(t.contact_name or '?')} · {e(t.contact_role or '')}\n"
        f"🏢 {e(t.company or 'UNKNOWN')}  ·  <code>{e(t.contact_email)}</code>\n"
        f"🧷 {e(t.note or '—')}\n\n"
        f"<b>Subject:</b> {e(t.subject or '')}\n"
        f"<blockquote>{e((t.email_draft or '')[:2500])}</blockquote>"
    )
