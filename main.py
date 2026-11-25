"""Entry point: initialises DB, runs the Telegram bot + scheduler."""

import os

import log as _log_mod
from dotenv import load_dotenv

load_dotenv()


def main():
    _log_mod.configure()
    log = _log_mod.get_logger("main")

    from db.session import create_tables
    create_tables()
    log.info("app.db_ready", path=os.getenv("DB_PATH", "data/jobs.db"))

    # The scheduler is started in bot.main.post_init, once the bot is running.
    from bot.main import build_app
    app = build_app()
    log.info("app.bot_starting")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import time

    # Telegram needs the VPN; if it drops, wait and reconnect instead of dying.
    while True:
        try:
            main()
            break
        except KeyboardInterrupt:
            break
        except Exception as exc:  # network errors from python-telegram-bot
            _log_mod.get_logger("main").error("app.crashed_retrying", error=str(exc)[:200])
            time.sleep(30)
