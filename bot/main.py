import os

import log as _log_mod
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.callbacks import handle_callback, handle_edit_text
from bot.auth import auth_required
from bot.outreach import import_contacts_cmd, outreach_cmd
from bot.commands import (
    cmd_pause, cmd_run, cmd_resume, cmd_settings,
    cmd_sources, cmd_start, cmd_stats, cmd_today,
)

log = _log_mod.get_logger("bot.main")


def build_app() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    builder = Application.builder().token(token)
    proxy = os.getenv("TELEGRAM_PROXY")
    if proxy:
        # e.g. http://127.0.0.1:1080 or socks5://127.0.0.1:1080 (needs httpx[socks])
        builder = builder.proxy(proxy).get_updates_proxy(proxy)
    builder = (
        builder.connect_timeout(30).read_timeout(30)
        .get_updates_connect_timeout(30).get_updates_read_timeout(30)
    )
    app = builder.build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("sources", cmd_sources))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("import", auth_required(import_contacts_cmd)))
    app.add_handler(CommandHandler("outreach", auth_required(outreach_cmd)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text))

    async def post_init(application):
        from scheduler.main import build_scheduler, job_health
        application.bot_data["scheduler"] = build_scheduler(application)
        application.bot_data["scheduler"].start()
        await job_health(application)

    app.post_init = post_init

    return app
