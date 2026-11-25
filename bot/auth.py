import os
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

import log as _log_mod
log = _log_mod.get_logger("bot.auth")


def _allowed_id() -> int:
    return int(os.getenv("TELEGRAM_USER_ID", "0"))


def auth_required(func):
    """Reject any update not from the configured TELEGRAM_USER_ID."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = None
        if update.message:
            uid = update.message.from_user.id
        elif update.callback_query:
            uid = update.callback_query.from_user.id

        if uid != _allowed_id():
            log.warning("bot.unauthorized", user_id=uid)
            return
        return await func(update, context)
    return wrapper
