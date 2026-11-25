import yaml

from bot.auth import auth_required
from bot.digest import send_digest
from db.models import Job
from db.session import session_scope
from telegram import Update
from telegram.ext import ContextTypes


@auth_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "👋 <b>Job Agent is live.</b>\n\n"
        "<b>Commands:</b>\n"
        "/today — daily digest\n"
        "/stats — application statistics\n"
        "/sources — enabled sources\n"
        "/pause — pause scheduler\n"
        "/resume — resume scheduler\n"
        "/settings — current settings\n"
        "/run — collect now\n"
        "/import — load data/contacts.csv for cold outreach\n"
        "/outreach — review cold-email drafts\n"
    )


@auth_required
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_digest(context.bot, update.effective_chat.id)


@auth_required
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def counts(is_k: bool):
        with session_scope() as db:
            q = db.query(Job).filter((Job.source == "karlancer") if is_k else (Job.source != "karlancer"))
            total = q.count()
            applied = q.filter(Job.status.in_(["applied", "approved"])).count()
            replies = q.filter(Job.status.in_(["replied", "interview"])).count()
        return total, applied, replies

    k, f = counts(True), counts(False)
    await update.message.reply_html(
        "<b>📊 Stats</b>\n\n"
        f"🟠 <b>Karlancer:</b> collected {k[0]} | approved {k[1]} | replies {k[2]}\n"
        f"🌍 <b>Foreign:</b> collected {f[0]} | approved {f[1]} | replies {f[2]}"
    )


@auth_required
async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger the collection pipelines now."""
    from scheduler.main import job_foreign, job_karlancer
    await update.message.reply_text("⏳ Running collection now…")
    await job_foreign(context.application)
    await job_karlancer(context.application)


@auth_required
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data["paused"] = True
    await update.message.reply_text("⏸ Scheduler paused.")


@auth_required
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data["paused"] = False
    await update.message.reply_text("▶️ Scheduler resumed.")


@auth_required
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("config.yaml") as f:
            cfg = yaml.safe_load(f)
        app_cfg = cfg.get("application", {})
        dry_run = app_cfg.get("dry_run", False)
        auto = app_cfg.get("auto_send", {})
        sources = cfg.get("sources", {})
        on = [k for k, v in sources.items() if v]
        await update.message.reply_html(
            "<b>⚙️ Settings</b>\n\n"
            f"Dry run: <code>{'ON ⚠️' if dry_run else 'OFF'}</code>\n"
            f"Active sources: {', '.join(on) or 'none'}\n\n"
            "<b>Auto-send (all OFF by default):</b>\n"
            f"  Karlancer proposals: {'ON' if auto.get('karlancer_proposals') else 'OFF'}\n"
            f"  Foreign applications: {'ON' if auto.get('foreign_applications') else 'OFF'}\n"
            f"  Cold emails: {'ON' if auto.get('cold_emails') else 'OFF'}"
        )
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Could not read config.yaml: {exc}")


def _sources() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f).get("sources", {})


@auth_required
async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "<b>🔌 Sources</b>\n\n"
        "<b>Karlancer:</b> 🟠 enabled (login required)\n\n"
        "<b>Foreign remote:</b>\n"
        + "\n".join(f"{'🔵' if on else '⚫'} {name}" for name, on in _sources().items())
    )
