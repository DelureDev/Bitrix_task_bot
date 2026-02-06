from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bitrix import BitrixClient
from bot_handlers import (
    build_conversation_handler,
    build_link_conversation_handler,
    cmd_cancel,
    cmd_me,
    cmd_start,
    hydrate_link,
    menu_router,
    maybe_show_menu,
)
from config import load_settings
from utils import ensure_dir
from usermap import UserMap


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    ensure_dir(settings.upload_dir)

    app = Application.builder().token(settings.tg_bot_token).build()

    # shared objects
    app.bot_data["settings"] = settings
    app.bot_data["bitrix"] = BitrixClient(settings.bitrix_webhook_base)

    usermap = UserMap(settings.usermap_db)
    usermap.init()
    app.bot_data["usermap"] = usermap

    # hydration: подтягиваем привязку из sqlite в user_data ДО любых проверок
    app.add_handler(MessageHandler(filters.ALL, hydrate_link), group=-1)

    # commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # menu router: ONLY HELP. BTN_LINK/BTN_CREATE are handled by ConversationHandlers.
    app.add_handler(
        MessageHandler(filters.Regex(r"^(ℹ️ Как найти ID\?)$"), menu_router),
        group=0,
    )

    # conversations
    app.add_handler(build_conversation_handler(), group=1)
    app.add_handler(build_link_conversation_handler(), group=1)

    # fallback: первое любое сообщение (только TEXT, не команда) -> показать меню один раз
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, maybe_show_menu), group=99)


    logging.getLogger(__name__).info("Bot started. Waiting for commands /start or /task")
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
