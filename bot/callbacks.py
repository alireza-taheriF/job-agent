import json
from html import escape as e

from telegram import Update
from telegram.ext import ContextTypes

import log as _log_mod
from agents.common import load_config
from bot.auth import auth_required
from bot.formatters import foreign_card, karlancer_card
from bot.keyboards import foreign_buttons, karlancer_buttons
from db.models import Application, FeedbackEvent, Job, Proposal
from db.session import session_scope

log = _log_mod.get_logger("bot.callbacks")


def _latest(job):
    return max(job.proposals, key=lambda p: p.version or 0, default=None)


@auth_required
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if ":" not in data:
        return
    action, raw_id = data.split(":", 1)
    if action in ("csend", "cskip") and raw_id.isdigit():
        from bot.outreach import outreach_callback
        await outreach_callback(query, action, int(raw_id))
        return

    with session_scope() as db:
        job = db.get(Job, int(raw_id)) if raw_id.isdigit() else None
        if not job:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("⚠️ Job not found.")
            return
        fa = job.source == "karlancer"
        prop = _latest(job)

        if action == "apply":
            await query.edit_message_reply_markup(reply_markup=None)
            app_row = Application(job_id=job.id, proposal_id=prop.id if prop else None,
                                  status="pending", submission_method="manual",
                                  dry_run=load_config()["application"]["dry_run"])
            db.add(app_row)
            job.status = "approved"
            db.add(FeedbackEvent(job_id=job.id, action="apply"))
            if fa:
                from agents.karlancer.collector import SessionError
                from agents.karlancer.submitter import submit_proposal
                try:
                    st, note = await submit_proposal(job.url, prop.content if prop else "")
                except (SessionError, RuntimeError) as exc:
                    st, note = "failed", str(exc)
                if st == "sent":
                    job.status = "applied"
                    await query.message.reply_text(f"📤 ارسال شد ({note})")
                    return
                if st in ("dry_run", "failed"):
                    await query.message.reply_text(f"ℹ️ {st}: {note}")
                text = (f"✅ <b>تأیید شد</b> — {e(job.title)}\n\n"
                        f"ارسال خودکار هنوز پیاده‌سازی نشده؛ متن زیر را در لینک ثبت کنید:\n{e(job.url)}\n\n"
                        f"<pre>{e(prop.content if prop else '')}</pre>")
            else:
                from agents.foreign.submitter import submit_application
                try:
                    st, note = submit_application(job, prop)
                except Exception as exc:
                    st, note = "failed", str(exc)[:300]
                if st == "sent":
                    job.status = "applied"
                    app_row.status, app_row.submission_method = "sent", "email"
                    await query.message.reply_text(f"📤 Sent by email ({note})")
                    return
                try:
                    letter = json.loads(prop.content).get("cover_letter", "")
                except (ValueError, AttributeError):
                    letter = prop.content if prop else ""
                text = (f"✅ <b>Approved</b> — {e(job.title)} @ {e(job.company or '')}\n"
                        f"ℹ️ {e(st)}: {e(note)}\n\nApply here:\n{e(job.url)}\n\n"
                        f"<pre>{e(letter)}</pre>")
            await query.message.reply_html(text, disable_web_page_preview=True)

        elif action == "skip":
            await query.edit_message_reply_markup(reply_markup=None)
            job.status = "skipped"
            db.add(FeedbackEvent(job_id=job.id, action="skip"))
            await query.message.reply_text("⏭ رد شد." if fa else "⏭ Skipped.")

        elif action == "edit":
            context.user_data["editing"] = job.id
            await query.message.reply_html(
                f"✏️ <b>{e(job.title)}</b>\n\n"
                + ("دستور ویرایش را بنویسید، مثلاً: <i>«کوتاه‌تر کن»</i>" if fa else
                   "Type your edit instruction, e.g. <i>'make it shorter'</i>"))

        elif action == "details":
            skills = ", ".join(json.loads(job.skills_json or "[]"))
            await query.message.reply_html(
                f"🔍 <b>{e(job.title)}</b>\n{e(job.company or '')}\n"
                f"Budget: {e(job.budget_raw or 'UNKNOWN')}\nSkills: {e(skills)}\n"
                f"Score: {job.fit_score}/100\n{e(job.score_reason or '')}\n{e(job.url)}",
                disable_web_page_preview=True)
        else:
            log.warning("bot.callback.unknown", data=data)


@auth_required
async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free-text message after pressing ✏️ → regenerate the draft."""
    job_id = context.user_data.pop("editing", None)
    if not job_id:
        return
    instruction = update.message.text
    await update.message.reply_text("⏳ …")
    with session_scope() as db:
        job = db.get(Job, job_id)
        prop = _latest(job)
        jd = {"title": job.title, "company": job.company, "description": job.description}
        if job.source == "karlancer":
            from agents.karlancer.proposer import draft_proposal
            content = await draft_proposal(jd, db, instruction, prop.content if prop else None)
        else:
            from agents.foreign.materials import generate_materials
            prev = ""
            try:
                prev = json.loads(prop.content).get("cover_letter", "")
            except (ValueError, AttributeError):
                pass
            content = json.dumps(await generate_materials(jd, db, instruction, prev), ensure_ascii=False)
        new = Proposal(job_id=job.id, content=content, version=(prop.version or 1) + 1 if prop else 1,
                       language=prop.language if prop else "en", edit_instruction=instruction)
        db.add(new)
        db.add(FeedbackEvent(job_id=job.id, action="edit", edit_instruction=instruction))
        db.flush()
        if job.source == "karlancer":
            text, kb = karlancer_card(job, new), karlancer_buttons(job.id)
        else:
            text, kb = foreign_card(job, new), foreign_buttons(job.id)
    await update.message.reply_html(text, reply_markup=kb, disable_web_page_preview=True)
