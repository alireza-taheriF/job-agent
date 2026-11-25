"""Telegram side of cold outreach: /import, /outreach and the Send/Skip buttons."""

from agents.common import ROOT
from agents.outreach import cold_email
from bot.formatters import outreach_card
from bot.keyboards import outreach_buttons
from db.models import ColdEmailTarget
from db.session import session_scope

CONTACTS = ROOT / "data" / "contacts.csv"


async def send_outreach_cards(bot, chat_id: int, draft_new: bool = True) -> int:
    with session_scope() as db:
        room = cold_email.remaining_today(db)
        if draft_new and room:
            await cold_email.draft_new(db, room)
        rows = (db.query(ColdEmailTarget)
                .filter(ColdEmailTarget.status.in_(("draft", "followup_draft")))
                .limit(max(room, 1)).all())
        cards = [(outreach_card(t), outreach_buttons(t.id)) for t in rows]
    if not cards:
        await bot.send_message(chat_id, "📭 No outreach drafts. Put contacts in data/contacts.csv and send /import.")
        return 0
    if not room:
        await bot.send_message(chat_id, "⏸ Daily cold-email limit reached; these can be sent tomorrow.")
    for text, kb in cards:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb,
                               disable_web_page_preview=True)
    return len(cards)


async def import_contacts_cmd(update, context):
    if not CONTACTS.exists():
        await update.message.reply_text(f"⚠️ {CONTACTS} not found (columns: company,name,role,email,linkedin,note)")
        return
    with session_scope() as db:
        res = cold_email.import_contacts(db, CONTACTS)
    await update.message.reply_text(f"📥 Imported {res['added']} contacts, skipped {res['skipped']} (no email or duplicate).")


async def outreach_cmd(update, context):
    await send_outreach_cards(context.bot, update.effective_chat.id)


async def outreach_callback(query, action: str, target_id: int):
    with session_scope() as db:
        t = db.get(ColdEmailTarget, target_id)
        if not t:
            await query.message.reply_text("⚠️ Contact not found.")
            return
        await query.edit_message_reply_markup(reply_markup=None)
        if action == "cskip":
            t.status = "skipped"
            await query.message.reply_text("⏭ Skipped.")
            return
        try:
            st, note = cold_email.send(db, t, approved=True)
        except Exception as exc:
            st, note = "failed", str(exc)[:300]
    await query.message.reply_text({"sent": "📤", "dry_run": "🧪"}.get(st, "ℹ️") + f" {st}: {note}")
