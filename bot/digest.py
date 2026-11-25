"""Send the shortlisted jobs to Telegram."""

from datetime import datetime, timedelta

from bot.formatters import foreign_card, karlancer_card
from bot.keyboards import foreign_buttons, karlancer_buttons
from db.models import Job
from db.session import session_scope


async def send_digest(bot, chat_id: int, only_new_hours: int | None = None) -> int:
    """Send shortlisted jobs. Returns the number of cards sent."""
    with session_scope() as db:
        q = db.query(Job).filter(Job.status == "shortlisted")
        if only_new_hours:
            q = q.filter(Job.collected_at >= datetime.utcnow() - timedelta(hours=only_new_hours))
        jobs = q.order_by(Job.fit_score.desc()).all()
        cards = []
        for j in jobs:
            p = max(j.proposals, key=lambda x: x.version or 0, default=None)
            if j.source == "karlancer":
                cards.append((karlancer_card(j, p), karlancer_buttons(j.id)))
            else:
                cards.append((foreign_card(j, p), foreign_buttons(j.id)))
    if not cards:
        await bot.send_message(chat_id, "📭 No shortlisted jobs right now.")
        return 0
    for text, kb in cards:
        await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb,
                               disable_web_page_preview=True)
    return len(cards)
