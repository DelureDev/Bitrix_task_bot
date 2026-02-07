from __future__ import annotations

import logging
import re

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bitrix import BitrixClient
from bot_handlers import (
    BTN_HELP,
    build_conversation_handler,
    build_link_conversation_handler,
    cmd_cancel,
    cmd_me,
    cmd_start,
    hydrate_link,
    maybe_show_menu,
    menu_router,
)
from config import load_settings
from usermap import UserMap
from utils import ensure_dir


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    logging.getLogger(__name__).info(
        "Config loaded: BITRIX_DISK_FOLDER_ID=%s, LOG_LEVEL=%s",
        settings.bitrix_disk_folder_id,
        settings.log_level,
    )

    ensure_dir(settings.upload_dir)

    app = Application.builder().token(settings.tg_bot_token).build()

    app.bot_data["settings"] = settings
    app.bot_data["bitrix"] = BitrixClient(
        settings.bitrix_webhook_base,
        timeout=settings.bitrix_http_timeout,
        upload_timeout=settings.bitrix_upload_timeout,
        upload_url_timeout=settings.bitrix_upload_url_timeout,
        small_upload_probe_timeout=settings.bitrix_small_upload_probe_timeout,
        small_upload_final_timeout=settings.bitrix_small_upload_final_timeout,
    )

    usermap = UserMap(settings.usermap_db)
    usermap.init()
    app.bot_data["usermap"] = usermap

    # Hydrate linked Bitrix profile from sqlite into user_data before checks.
    app.add_handler(MessageHandler(filters.ALL, hydrate_link), group=-1)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Route only the help button here. Link/create are handled by conversations.
    app.add_handler(
        MessageHandler(filters.Regex(rf"^{re.escape(BTN_HELP)}$"), menu_router),
        group=0,
    )

    app.add_handler(build_conversation_handler(), group=1)
    app.add_handler(build_link_conversation_handler(), group=1)

    # Fallback: show menu once on the first plain text message.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, maybe_show_menu), group=99)

    logging.getLogger(__name__).info("Bot started. Waiting for commands /start or /task")
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
