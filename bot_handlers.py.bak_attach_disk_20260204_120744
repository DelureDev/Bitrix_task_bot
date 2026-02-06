from __future__ import annotations

import logging
import datetime
logger = logging.getLogger(__name__)
import os
import re
from dataclasses import dataclass
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bitrix import BitrixClient, BitrixError
from config import Settings
from utils import make_ticket_id, safe_filename
from storage import build_upload_dir, make_local_path, SavedFile
log = logging.getLogger(__name__)

BTN_CREATE = "📝 Создать задачу"
BTN_LINK = "🔗 Привязать профиль"

MAIN_MENU = ReplyKeyboardMarkup(
    [[BTN_CREATE, BTN_LINK]],
    resize_keyboard=True
)

LINK_WAIT = 9901

def parse_bitrix_user_id(text: str) -> int | None:
    t = (text or "").strip()
    # allow just number
    if t.isdigit():
        return int(t)
    # allow profile URL with /user/123/
    m = re.search(r"/user/(\d+)/", t)
    if m:
        return int(m.group(1))
    # fallback: user/123 (without trailing slash)
    m = re.search(r"user/(\d+)", t)
    if m:
        return int(m.group(1))
    return None

def is_linked(context, tg_id: int) -> int | None:
    pass


async def _show_link_required_old_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "\n".join([
            "Сначала нужно привязать профиль Bitrix24,",
            "иначе задачи будут создаваться от технического пользователя.",
            "",
            "Нажмите «🔗 Привязать профиль» и пришлите ссылку на ваш профиль или просто число ID."
        ]),
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END

async def help_find_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "\n".join([
            "Как найти ваш ID в Bitrix24:",
            "1) Откройте Bitrix24: https://fantasyclinic.bitrix24.ru/",
            "2) Нажмите на своё имя/аватар → Профиль",
            "3) В адресной строке будет .../company/personal/user/123/ — число 123 и есть ваш ID",
            "",
            "Можно прислать боту ссылку целиком или просто число."
        ]),
        reply_markup=MAIN_MENU
    )

    try:
        usermap = context.application.bot_data.get("usermap")
        return usermap.get(tg_id) if usermap else None
    except Exception:
        return None


async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["_menu_shown"] = True
    await update.message.reply_text(
        "\n".join([
            "Привязка профиля Bitrix24:",
            "Пришлите ссылку на ваш профиль или просто число ID.",
            "",
            "Пример ссылки:",
            "https://fantasyclinic.bitrix24.ru/company/personal/user/123/",
            "или просто: 123"
        ]),
        reply_markup=MAIN_MENU
    )
    return LINK_WAIT


async def link_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    bitrix_user_id = parse_bitrix_user_id(update.message.text)
    if not bitrix_user_id:
        await update.message.reply_text(
            "Не понял ID. Пришлите ссылку вида .../user/123/ или просто число 123.",
            reply_markup=MAIN_MENU
        )
        return LINK_WAIT

    usermap = context.application.bot_data["usermap"]
    usermap.set(update.effective_user.id, bitrix_user_id)
    usermap.set(str(update.effective_user.id), bitrix_user_id)

    await update.message.reply_text(
        f"Ок ✅ Профиль привязан. Ваш Bitrix ID: {bitrix_user_id}",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END

def build_link_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("link", link_start),
            MessageHandler(filters.Regex("^" + re.escape(BTN_LINK) + "$"), link_start),
        ],
        states={
            LINK_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_receive)]
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )




def _extract_bitrix_user_id(text: str) -> int | None:
    # ожидаем ссылку профиля вида .../company/personal/user/123/...
    m = re.search(r"/user/(\d+)/", text)
    if m:
        return int(m.group(1))
    # fallback: если скопировали без завершающего /
    m = re.search(r"user/(\d+)", text)
    if m:
        return int(m.group(1))
    return None


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return

    if not context.args:
        msg = (
            "Привязка Bitrix профиля:\n"
            "1) Откройте свой профиль в Bitrix24\n"
            "2) Скопируйте ссылку вида https://.../company/personal/user/123/\n"
            "3) Отправьте команду: /link <ссылка>\n\n"
            "Пример:\n"
            "/link https://fantasyclinic.bitrix24.ru/company/personal/user/123/"
        )
        await update.message.reply_text(msg)
        return

    url = " ".join(context.args).strip()
    bitrix_user_id = _extract_bitrix_user_id(url)
    if not bitrix_user_id:
        await update.message.reply_text("Не смог распознать ID из ссылки. Нужна ссылка с /user/123/ внутри.")
        return

    usermap = context.application.bot_data["usermap"]
    usermap.set(update.effective_user.id, bitrix_user_id)
    usermap.set(str(update.effective_user.id), bitrix_user_id)
    await update.message.reply_text(f"Ок ✅ Привязал. Ваш Bitrix ID: {bitrix_user_id}")

WAIT_TITLE, WAIT_DESCRIPTION, WAIT_ATTACHMENTS, CONFIRM = range(4)


def _kb_start():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Создать задачу", callback_data="start_task")]])


def _kb_attachments():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Готово ✅", callback_data="attachments_done")],
            [InlineKeyboardButton("Отмена ❌", callback_data="cancel_task")],
        ]
    )


def _kb_confirm():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Создать ✅", callback_data="confirm_create")],
            [InlineKeyboardButton("Отмена ❌", callback_data="cancel_task")],
        ]
    )


def _is_allowed(settings, tg_user_id: int) -> bool:
    if not settings.allowed_tg_users:
        return True
    return tg_user_id in settings.allowed_tg_users


def build_task_description(user_desc: str, initiator_block: str, attachments_block: str) -> str:
    parts = [
        user_desc.strip(),
        "",
        initiator_block.strip(),
        "",
        attachments_block.strip(),
    ]
    return "\n".join(parts).strip()


def build_initiator_block(update: Update) -> str:
    u = update.effective_user
    username = f"@{u.username}" if (u and u.username) else ""
    if not username:
        username = f"tg_id:{u.id}" if u else "-"
    return "Контакт инициатора:\nTelegram: " + username


def build_attachments_block(files: List[SavedFile], upload_root: str) -> str:
    if not files:
        return "Вложения:\n- (нет)"
    lines = ["Вложения (сохранены на сервере):"]
    for f in files:
        # показываем относительный путь от корня проекта, чтобы читалось
        rel = os.path.relpath(f.local_path, start=os.getcwd())
        lines.append(f"- {f.original_name} -> {rel}")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["_menu_shown"] = True
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text("Привет! Нажми кнопку или используй /task чтобы создать задачу.", reply_markup=_kb_start())



async def maybe_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню только один раз (первое сообщение в чате), без спама."""
    try:
        if context.user_data.get("_menu_shown"):
            return
        context.user_data["_menu_shown"] = True
    except Exception:
        return

    txt = (getattr(getattr(update, "message", None), "text", None) or "").strip()
    # не перехватываем тексты кнопок — их обработают основные хэндлеры/ConversationHandler
    if txt in (BTN_CREATE, BTN_LINK, BTN_HELP):
        return

    await cmd_start(update, context)

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["_menu_shown"] = True
    logger.info('HIT cmd_task tg_id=%s text=%s', update.effective_user.id if update and getattr(update,'effective_user',None) else None, update.message.text if update and getattr(update,'message',None) else None)

    linked = is_linked(context, update.effective_user.id)
    if not linked:
        await show_link_required(update, context)
        return ConversationHandler.END


    # Жёсткое требование: без привязки профиля нельзя создавать задачи
    linked = is_linked(context, update.effective_user.id)
    if not linked:
        await update.message.reply_text(
            "\n".join([
                "Перед созданием задач нужно один раз привязать профиль Bitrix24.",
                "Нажмите кнопку «🔗 Привязать профиль» и пришлите ссылку/ID.",
            ]),
            reply_markup=MAIN_MENU
        )
        return ConversationHandler.END


    # Требуем привязку Bitrix профиля
    try:
        usermap = context.application.bot_data.get("usermap")
        linked = usermap.get(update.effective_user.id) if usermap else None
    except Exception:
        linked = None

    if not linked:
        await update.message.reply_text(
            "Перед созданием задач нужно один раз привязать профиль Bitrix24.\n"
            "Команда:\n"
            "/link <ссылка на ваш профиль>\n\n"
            "Пример:\n"
            "/link https://fantasyclinic.bitrix24.ru/company/personal/user/123/\n\n"
            "После привязки снова нажмите /task."
        )
        return ConversationHandler.END

    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return ConversationHandler.END

    context.user_data.clear()
    ticket_id = make_ticket_id()
    context.user_data["ticket_id"] = ticket_id
    context.user_data["files"] = []
    await update.message.reply_text("Ок. Введи *Название* задачи:", parse_mode="Markdown")
    return WAIT_TITLE


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Отменено.")
    return ConversationHandler.END


async def cb_start_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    fake_update = update
    # Запускаем как /task
    context.user_data.clear()
    ticket_id = make_ticket_id()
    context.user_data["ticket_id"] = ticket_id
    context.user_data["files"] = []
    await query.message.reply_text("Ок. Введи *Название* задачи:", parse_mode="Markdown")
    return WAIT_TITLE


async def on_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text("Название пустое. Введи название ещё раз:")
        return WAIT_TITLE
    context.user_data["title"] = title
    await update.message.reply_text("Теперь введи *Описание* (что сделать/что не работает/контекст):", parse_mode="Markdown")
    return WAIT_DESCRIPTION


async def on_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc = (update.message.text or "").strip()
    if not desc:
        await update.message.reply_text("Описание пустое. Введи описание ещё раз:")
        return WAIT_DESCRIPTION
    context.user_data["description"] = desc
    await update.message.reply_text(
        "Теперь можешь отправить *скриншоты/файлы* (можно несколько). Когда закончишь — нажми *Готово ✅*.",
        parse_mode="Markdown",
        reply_markup=_kb_attachments(),
    )
    return WAIT_ATTACHMENTS


async def on_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.application.bot_data["settings"]
    tg_user_id = update.effective_user.id
    ticket_id = context.user_data.get("ticket_id")
    if not ticket_id:
        await update.message.reply_text("Сессия не найдена. Запусти /task заново.")
        return ConversationHandler.END

    date_str = datetime.date.today().isoformat()
    upload_dir = build_upload_dir(settings.upload_dir, date_str, tg_user_id, ticket_id)

    await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    saved: List[SavedFile] = context.user_data.get("files", [])

    # Photo
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        filename = f"photo_{photo.file_unique_id}.jpg"
        local_path = make_local_path(upload_dir, filename)
        await file.download_to_drive(custom_path=local_path)
        saved.append(SavedFile(original_name=filename, local_path=local_path))
        context.user_data["files"] = saved
        await update.message.reply_text(f"Ок, сохранил фото: {filename}")
        return WAIT_ATTACHMENTS

    # Document
    if update.message.document:
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        original = doc.file_name or f"document_{doc.file_unique_id}"
        filename = safe_filename(original)
        local_path = make_local_path(upload_dir, filename)
        await file.download_to_drive(custom_path=local_path)
        saved.append(SavedFile(original_name=original, local_path=local_path))
        context.user_data["files"] = saved
        await update.message.reply_text(f"Ок, сохранил файл: {original}")
        return WAIT_ATTACHMENTS

    await update.message.reply_text("Я могу принять фото или документ. Пришли файл/скриншот или нажми Готово ✅.")
    return WAIT_ATTACHMENTS


async def cb_attachments_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    title = context.user_data.get("title", "")
    files: List[SavedFile] = context.user_data.get("files", [])
    await query.message.reply_text(
        f"Проверим перед созданием:\n\n*Название:* {title}\n*Вложений:* {len(files)}\n\nНажми *Создать ✅* или *Отмена ❌*.",
        parse_mode="Markdown",
        reply_markup=_kb_confirm(),
    )
    return CONFIRM


async def cb_cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.message.reply_text("Отменено.")
    return ConversationHandler.END


def _task_link(settings, task_id: int) -> str:
    tpl = (settings.bitrix_task_url_template or "").strip()
    if tpl:
        return tpl.format(task_id=task_id)

    # Fallback: if portal base exists, try a common pattern (may differ on your portal)
    base = (settings.bitrix_portal_base or "").strip().rstrip("/")
    if base:
        rid = settings.bitrix_default_responsible_id
        return f"{base}/company/personal/user/{rid}/tasks/task/view/{task_id}/"
    return ""


async def cb_confirm_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    settings = context.application.bot_data["settings"]
    bitrix: BitrixClient = context.application.bot_data["bitrix"]

    title = (context.user_data.get("title") or "").strip()
    user_desc = (context.user_data.get("description") or "").strip()
    files: List[SavedFile] = context.user_data.get("files", [])

    if not title or not user_desc:
        await query.message.reply_text("Не хватает данных. Запусти /task заново.")
        context.user_data.clear()
        return ConversationHandler.END

    initiator = build_initiator_block(update)
    attachments = build_attachments_block(files, settings.upload_dir)
    full_desc = build_task_description(user_desc, initiator, attachments)

    await query.message.reply_text("Создаю задачу в Bitrix24…")

    created_by = None

    # Если нет привязки — не создаём задачу (жёсткое требование)
    if created_by is None:
        await query.message.reply_text(
            "Нельзя создать задачу без привязки профиля Bitrix24.\n"
            "Сначала сделайте:\n"
            "/link <ссылка на ваш профиль>\n\n"
            "Пример:\n"
            "/link https://fantasyclinic.bitrix24.ru/company/personal/user/123/"
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        usermap = context.application.bot_data.get("usermap")
        if usermap:
            created_by = usermap.get(update.effective_user.id)
    except Exception:
        created_by = None

    try:
        task_id = await bitrix.create_task(
            title=title,
            description=full_desc,
            responsible_id=settings.bitrix_default_responsible_id,
            group_id=settings.bitrix_group_id,
            priority=settings.bitrix_priority,
            created_by=created_by,
        )
    except BitrixError as e:
        # Если Bitrix не разрешил CREATED_BY — пробуем создать без него
        if created_by is not None:
            log.warning("Bitrix rejected CREATED_BY=%s, retrying without it: %s %s", created_by, e.message, e.details)
            try:
                task_id = await bitrix.create_task(
                    title=title,
                    description=full_desc,
                    responsible_id=settings.bitrix_default_responsible_id,
                    group_id=settings.bitrix_group_id,
                    priority=settings.bitrix_priority,
                    created_by=None,
                )
            except BitrixError as e2:
                log.exception("Bitrix error (retry without CREATED_BY)")
                await query.message.reply_text("\n".join(["Не получилось создать задачу.", f"Ошибка: {e2.message}", str(e2.details)]))
                context.user_data.clear()
                return ConversationHandler.END
            except Exception as e2:
                log.exception("Unexpected error (retry without CREATED_BY)")
                await query.message.reply_text(f"Не получилось создать задачу. Ошибка: {e2}")
                context.user_data.clear()
                return ConversationHandler.END
        else:
            log.exception("Bitrix error")
            await query.message.reply_text("\n".join(["Не получилось создать задачу.", f"Ошибка: {e.message}", str(e.details)]))
            context.user_data.clear()
            return ConversationHandler.END
    except Exception as e:
        log.exception("Unexpected error")
        await query.message.reply_text(f"Не получилось создать задачу. Ошибка: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    link = _task_link(settings, task_id)
    if link:
        await query.message.reply_text("\n".join(["Задача создана ✅", f"ID: {task_id}", f"Ссылка: {link}"]))
    else:
        await query.message.reply_text("\n".join(["Задача создана ✅", f"ID: {task_id}", "(Ссылку можно добавить через BITRIX_TASK_URL_TEMPLATE в .env)"]))

    context.user_data.clear()
    return ConversationHandler.END



def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("task", cmd_task),
              MessageHandler(filters.Regex(r"^📝 Создать задачу$"), cmd_task),
            CallbackQueryHandler(cb_start_task, pattern="^start_task$"),
        ],
        states={
            WAIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_title)],
            WAIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_description)],
            WAIT_ATTACHMENTS: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, on_attachment),
                CallbackQueryHandler(cb_attachments_done, pattern="^attachments_done$"),
                CallbackQueryHandler(cb_cancel_task, pattern="^cancel_task$"),
            ],
            CONFIRM: [
                CallbackQueryHandler(cb_confirm_create, pattern="^confirm_create$"),
                CallbackQueryHandler(cb_cancel_task, pattern="^cancel_task$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

async def _menu_router_old_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        # старт создания задачи как /task (используем существующий cmd_task если есть)
        linked = is_linked(context, update.effective_user.id)
        if not linked:
            await show_link_required(update, context)
            return
        # если есть cmd_task - вызываем его
        if "cmd_task" in globals():
            await cmd_task(update, context)  # type: ignore
        else:
            await update.message.reply_text("Команда создания задачи не найдена. Используйте /task.", reply_markup=MAIN_MENU)
        return

    # если непонятно что нажали
    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)


# === UX_MENU_PATCH_V1 ===
# Меню кнопками: Создать задачу / Привязать профиль / Как найти ID
# Не лезем в существующую логику задач: только добавляем UX-обвязку и жёсткий блок без привязки.

# Если каких-то импортов нет (из-за прошлых патчей) — пробуем подтянуть их мягко:
try:
    ReplyKeyboardMarkup
except NameError:
    from telegram import ReplyKeyboardMarkup

try:
    MessageHandler
    filters
except NameError:
    from telegram.ext import MessageHandler, filters

import re as _re

BTN_CREATE = "📝 Создать задачу"
BTN_LINK = "🔗 Привязать профиль"
BTN_HELP = "ℹ️ Как найти ID?"

MAIN_MENU = ReplyKeyboardMarkup(
    [[BTN_CREATE, BTN_LINK], [BTN_HELP]],
    resize_keyboard=True
)

LINK_WAIT = 9901

def _parse_bitrix_user_id(text: str) -> int | None:
    t = (text or "").strip()
    if t.isdigit():
        return int(t)
    m = _re.search(r"/user/(\d+)/", t)
    if m:
        return int(m.group(1))
    m = _re.search(r"user/(\d+)", t)
    if m:
        return int(m.group(1))
    return None

def _is_linked(context, tg_id: int) -> int | None:
    try:
        um = context.application.bot_data.get("usermap")
        if not um:
            return None
        # пробуем int и str ключи
        v = um.get(tg_id)
        if v is not None:
            return v
        v = um.get(str(tg_id))
        if v is not None:
            return v
        return None
    except Exception:
        return None

async def show_link_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "\n".join([
            "Сначала привяжите профиль Bitrix24 ✅",
            "Иначе задачи будут создаваться от технического пользователя.",
            "",
            "Нажмите «🔗 Привязать профиль»."
        ]),
        reply_markup=MAIN_MENU
    )

async def help_find_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "\n".join([
            "Как найти ID в Bitrix24:",
            "1) Откройте Bitrix24: https://fantasyclinic.bitrix24.ru/",
            "2) Нажмите на своё имя/аватар → Профиль",
            "3) В адресной строке будет .../company/personal/user/123/ — число 123 и есть ваш ID",
            "",
            "Можно прислать ссылку целиком или просто число."
        ]),
        reply_markup=MAIN_MENU
    )

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "\n".join([
            "Привязать профиль Bitrix24:",
            "Пришлите ссылку на ваш профиль или просто число ID.",
            "",
            "Пример:",
            "https://fantasyclinic.bitrix24.ru/company/personal/user/123/",
            "или: 123"
        ]),
        reply_markup=MAIN_MENU
    )
    return LINK_WAIT

async def link_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    bitrix_user_id = _parse_bitrix_user_id(update.message.text)
    if not bitrix_user_id:
        await update.message.reply_text(
            "Не понял ID. Пришлите ссылку вида .../user/123/ или просто число 123.",
            reply_markup=MAIN_MENU
        )
        return LINK_WAIT

    usermap = context.application.bot_data["usermap"]
    usermap.set(update.effective_user.id, bitrix_user_id)
    usermap.set(str(update.effective_user.id), bitrix_user_id)

    await update.message.reply_text(
        f"Готово ✅ Профиль привязан (Bitrix ID: {bitrix_user_id}).\nТеперь нажмите «{BTN_CREATE}».",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END

def build_link_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^" + _re.escape(BTN_LINK) + "$"), link_start),
            CommandHandler("link", link_start),
        ],
        states={LINK_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_receive)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

async def _menu_router_old_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        linked = _is_linked(context, update.effective_user.id)
        if not linked:
            await show_link_required(update, context)
            return

        # Запускаем существующий обработчик задач, если он есть.
        if "cmd_task" in globals():
            handler = globals().get("_cmd_task_impl") or globals().get("cmd_task")
        if handler:
            await handler(update, context)  # type: ignore
        else:
            await update.message.reply_text("Создание задачи сейчас недоступно. Используйте /task.", reply_markup=MAIN_MENU)
        return

    # Любой другой текст — просто покажем меню
    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)

# cmd_start (если раньше отсутствовал/сломался) — создаём заново
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выберите действие:", reply_markup=MAIN_MENU)

# Жёсткий блок: если кто-то всё же идёт через /task — запретим без привязки
if "cmd_task" in globals():
    _cmd_task_impl = globals()["cmd_task"]
    async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # type: ignore
        linked = _is_linked(context, update.effective_user.id)
        if not linked:
            await show_link_required(update, context)
            return ConversationHandler.END
        return await _cmd_task_impl(update, context)  # type: ignore
# === /UX_MENU_PATCH_V1 ===


# === UX_MENU_PATCH_V2 ===
# Фикс: привязка не находилась из-за разъезда ключей/объекта мапы.
# Делаем универсальный getter/setter и переопределяем menu_router/link_receive.

try:
    MessageHandler
    filters
except NameError:
    from telegram.ext import MessageHandler, filters

import re as _re2

def _mapping_obj(context):
    bd = context.application.bot_data
    for k in ("usermap", "user_map", "tg_map", "tg_bitrix_map", "mapping"):
        obj = bd.get(k)
        if obj is None:
            continue
        # dict или объект с get/set
        if isinstance(obj, dict):
            return obj, k
        if hasattr(obj, "get") and (hasattr(obj, "set") or hasattr(obj, "__setitem__")):
            return obj, k
    # если ничего не нашли — создаём dict
    bd["usermap"] = {}
    return bd["usermap"], "usermap"

def _map_set(context, tg_id: int, bitrix_id: int):
    obj, _k = _mapping_obj(context)
    bid = int(bitrix_id)
    tid_int = int(tg_id)
    tid_str = str(tg_id)

    if isinstance(obj, dict):
        obj[tid_str] = bid
        obj[tid_int] = bid
        return

    # объект-обёртка (sqlite и т.п.)
    if hasattr(obj, "set"):
        obj.set(tid_str, bid)
        obj.set(tid_int, bid)
        return

    # fallback на __setitem__
    obj[tid_str] = bid
    obj[tid_int] = bid

def _map_get(context, tg_id: int) -> int | None:
    obj, _k = _mapping_obj(context)
    tid_int = int(tg_id)
    tid_str = str(tg_id)

    if isinstance(obj, dict):
        return obj.get(tid_int) or obj.get(tid_str)

    try:
        v = obj.get(tid_int)
        if v is None:
            v = obj.get(tid_str)
        return v
    except Exception:
        return None

# переопределяем link_receive, чтобы точно писало туда же, откуда читаем
async def link_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    text = update.message.text or ""
    bitrix_user_id = _parse_bitrix_user_id(text) if "_parse_bitrix_user_id" in globals() else None
    if not bitrix_user_id:
        # fallback parse
        t = text.strip()
        if t.isdigit():
            bitrix_user_id = int(t)
        else:
            m = _re2.search(r"/user/(\d+)/", t)
            bitrix_user_id = int(m.group(1)) if m else None

    if not bitrix_user_id:
        await update.message.reply_text(
            "Не понял ID. Пришлите ссылку вида .../user/123/ или просто число 123.",
            reply_markup=MAIN_MENU
        )
        return LINK_WAIT

    _map_set(context, update.effective_user.id, int(bitrix_user_id))

    await update.message.reply_text(
        "Готово ✅ Профиль привязан.\nТеперь нажмите «📝 Создать задачу».",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END

# переопределяем menu_router: проверка теперь через _map_get

async def _menu_router_old_3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        linked = _map_get(context, update.effective_user.id)
        if not linked:
            await show_link_required(update, context)
            return

        handler = globals().get("_cmd_task_impl") or globals().get("cmd_task")
        if handler:
            await handler(update, context)  # type: ignore
        else:
            await update.message.reply_text(
                "Создание задачи сейчас недоступно. Используйте /task.",
                reply_markup=MAIN_MENU
            )
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)

async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    bid = _map_get(context, tg_id)
    await update.message.reply_text(f"TG ID: {tg_id}\nBitrix ID (linked): {bid}", reply_markup=MAIN_MENU)
# === /UX_MENU_PATCH_V2 ===


# === UX_MENU_PATCH_V3 ===
# Финальный фикс: кнопка "Создать задачу" и /task проверяют привязку одинаково (через _map_get),
# и вызывают оригинальный обработчик задач без старых конфликтующих guard'ов.

def _linked_id(context, tg_id: int) -> int | None:
    # если V2 существует — используем её
    if "_map_get" in globals():
        return globals()["_map_get"](context, tg_id)  # type: ignore
    # fallback на старое, если вдруг V2 нет
    if "_is_linked" in globals():
        return globals()["_is_linked"](context, tg_id)  # type: ignore
    return None

# достаём "настоящий" обработчик задач:
# в V1 он сохранялся как _cmd_task_impl до переопределения cmd_task
_ORIG_TASK_HANDLER = globals().get("_cmd_task_impl") or globals().get("cmd_task")

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # type: ignore
    linked = _linked_id(context, update.effective_user.id)
    if not linked:
        await show_link_required(update, context)
        return ConversationHandler.END
    # вызываем оригинал
    if _ORIG_TASK_HANDLER:
        return await _ORIG_TASK_HANDLER(update, context)  # type: ignore
    await update.message.reply_text("Создание задачи сейчас недоступно. Используйте /task позже.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('HIT menu_router tg_id=%s text=%s', update.effective_user.id if update and getattr(update,'effective_user',None) else None, update.message.text if update and getattr(update,'message',None) else None)
    text = (update.message.text or "").strip()

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        linked = _linked_id(context, update.effective_user.id)
        if not linked:
            await show_link_required(update, context)
            return
        # запускаем задачу через cmd_task (уже с правильной проверкой)
        await cmd_task(update, context)
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)
# === /UX_MENU_PATCH_V3 ===


# === UX_HOTFIX_FINAL ===

# === UX_HOTFIX_FINAL ===
# Единая логика: /me и Create используют одну и ту же мапу (_map_get).
# Кнопка "Создать задачу" просто запускает /task (cmd_task), без старых веток.

# Сохраняем исходный обработчик создания задачи (тот, который реально ведёт диалог)
_ORIG_TASK_HANDLER = globals().get("_cmd_task_impl") or globals().get("cmd_task")

def _linked_bitrix_id(context, tg_id: int):
    mg = globals().get("_map_get")
    if mg:
        return mg(context, tg_id)  # type: ignore
    return None

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # type: ignore
    linked = _linked_bitrix_id(context, update.effective_user.id)
    if not linked:
        # show_link_required у нас остался один (после дедупа)
        await show_link_required(update, context)
        return ConversationHandler.END

    if _ORIG_TASK_HANDLER and _ORIG_TASK_HANDLER is not cmd_task:
        return await _ORIG_TASK_HANDLER(update, context)  # type: ignore

    await update.message.reply_text("Создание задачи временно недоступно. Напишите /start.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        # запускаем создание через cmd_task — единственная точка входа
        await cmd_task(update, context)
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)
# === /UX_HOTFIX_FINAL ===


# === MENU_ROUTER_FORCE_V4 ===

# === MENU_ROUTER_FORCE_V4 ===
# Единая проверка привязки как у /me: через _map_get(context, tg_id)

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    uid = update.effective_user.id

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_LINK:
        await link_start(update, context)
        return

    if text == BTN_CREATE:
        linked = _map_get(context, uid) if "_map_get" in globals() else None
        if not linked:
            await show_link_required(update, context)
            return
        # стартуем создание задачи
        await cmd_task(update, context)
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU)
# === /MENU_ROUTER_FORCE_V4 ===


# --- hydration: sqlite map -> context.user_data ---
from telegram import Update
from telegram.ext import ContextTypes

async def hydrate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Подтягивает Bitrix ID из sqlite (tg_bitrix_map) в context.user_data["bitrix_user_id"].
    Это чинит ситуации, когда /me видит привязку, а создание задачи проверяет user_data.
    """
    try:
        if not getattr(update, "effective_user", None):
            return
        tg_id = int(update.effective_user.id)
    except Exception:
        return

    try:
        bid = _map_get(context, tg_id)  # _map_get уже есть в файле
    except Exception:
        bid = None

    if bid:
        context.user_data["bitrix_user_id"] = int(bid)

# =============================================================================
# CLEAN_ARCH_V1 (single source of truth + no handler duplication)
# =============================================================================

def _kb_main_menu() -> ReplyKeyboardMarkup:
    # /start: только 2 кнопки, как в требованиях
    return ReplyKeyboardMarkup([[BTN_CREATE, BTN_LINK]], resize_keyboard=True)


def _kb_link_required() -> ReplyKeyboardMarkup:
    # Экран "сначала привяжите": LINK + HELP
    return ReplyKeyboardMarkup([[BTN_LINK], [BTN_HELP]], resize_keyboard=True)


def get_linked_bitrix_id(context: ContextTypes.DEFAULT_TYPE, tg_id: int) -> int | None:
    """
    Single source of truth.
    Всегда читает sqlite через UserMap (tg_bitrix_map).
    Может мягко кэшировать в context.user_data (но это НЕ источник истины).
    """
    try:
        usermap = context.application.bot_data.get("usermap")
        linked = usermap.get(int(tg_id)) if usermap else None
    except Exception:
        linked = None

    # мягкий кэш (не источник истины)
    try:
        if linked is not None:
            context.user_data["bitrix_user_id"] = int(linked)
        else:
            context.user_data.pop("bitrix_user_id", None)
    except Exception:
        pass

    return int(linked) if linked is not None else None


def is_linked(context, tg_id: int) -> int | None:
    # совместимость: старое имя, но теперь работает корректно
    return get_linked_bitrix_id(context, tg_id)


async def show_link_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update and update.effective_user else None
    log.info("HIT show_link_required tg_id=%s linked=%s", uid, get_linked_bitrix_id(context, uid) if uid else None)
    await update.message.reply_text(
        "\n".join(
            [
                "Сначала привяжите профиль Bitrix24 ✅",
                "",
                "Нажмите «🔗 Привязать профиль» и пришлите ссылку на ваш профиль или число ID.",
            ]
        ),
        reply_markup=_kb_link_required(),
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text("Выберите действие:", reply_markup=_kb_main_menu())


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    bid = get_linked_bitrix_id(context, tg_id)
    await update.message.reply_text(f"TG ID: {tg_id}\nBitrix ID (linked): {bid}", reply_markup=_kb_main_menu())


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update and update.effective_user else None
    text = (update.message.text or "").strip()
    linked = get_linked_bitrix_id(context, uid) if uid else None
    log.info("HIT menu_router tg_id=%s text=%s linked=%s", uid, text, linked)

    if text == BTN_HELP:
        await help_find_id(update, context)
        return

    if text == BTN_CREATE:
        # единая точка входа в создание (cmd_task сам проверит привязку)
        await cmd_task(update, context)
        return

    # BTN_LINK не обрабатываем здесь специально:
    # его должен ловить link ConversationHandler, иначе будет двойной prompt.
    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=_kb_main_menu())


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    linked = get_linked_bitrix_id(context, uid)
    log.info("HIT cmd_task tg_id=%s text=%s linked=%s", uid, update.message.text if update.message else None, linked)

    if not linked:
        await show_link_required(update, context)
        return ConversationHandler.END

    # дальше — ваша существующая логика диалога задач (минимально меняем)
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, uid):
        await update.message.reply_text("Доступ запрещён.")
        return ConversationHandler.END

    context.user_data.clear()
    ticket_id = make_ticket_id()
    context.user_data["ticket_id"] = ticket_id
    context.user_data["files"] = []
    await update.message.reply_text("Ок. Введи *Название* задачи:", parse_mode="Markdown")
    return WAIT_TITLE


# ВАЖНО: confirm_create у вас всегда упирался в блок "created_by is None" до вычисления usermap.
# Исправляем минимально: берём created_by из sqlite через единый helper.
async def cb_confirm_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    settings = context.application.bot_data["settings"]
    bitrix: BitrixClient = context.application.bot_data["bitrix"]

    title = (context.user_data.get("title") or "").strip()
    user_desc = (context.user_data.get("description") or "").strip()
    files: List[SavedFile] = context.user_data.get("files", [])

    if not title or not user_desc:
        await query.message.reply_text("Не хватает данных. Запусти /task заново.")
        context.user_data.clear()
        return ConversationHandler.END

    initiator = build_initiator_block(update)
    attachments = build_attachments_block(files, settings.upload_dir)
    full_desc = build_task_description(user_desc, initiator, attachments)

    await query.message.reply_text("Создаю задачу в Bitrix24…")

    created_by = get_linked_bitrix_id(context, update.effective_user.id)
    log.info("HIT cb_confirm_create tg_id=%s created_by=%s", update.effective_user.id, created_by)

    if created_by is None:
        await query.message.reply_text(
            "Нельзя создать задачу без привязки профиля Bitrix24.\n"
            "Сначала нажмите «🔗 Привязать профиль» и пришлите ID/ссылку."
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        task_id = await bitrix.create_task(
            title=title,
            description=full_desc,
            responsible_id=settings.bitrix_default_responsible_id,
            group_id=settings.bitrix_group_id,
            priority=settings.bitrix_priority,
            created_by=created_by,
        )
    except BitrixError as e:
        log.warning("Bitrix rejected CREATED_BY=%s, retrying without it: %s %s", created_by, e.message, e.details)
        try:
            task_id = await bitrix.create_task(
                title=title,
                description=full_desc,
                responsible_id=settings.bitrix_default_responsible_id,
                group_id=settings.bitrix_group_id,
                priority=settings.bitrix_priority,
                created_by=None,
            )
        except Exception as e2:
            log.exception("Bitrix error (retry without CREATED_BY)")
            await query.message.reply_text(f"Не получилось создать задачу. Ошибка: {e2}")
            context.user_data.clear()
            return ConversationHandler.END
    except Exception as e:
        log.exception("Unexpected error")
        await query.message.reply_text(f"Не получилось создать задачу. Ошибка: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    link = _task_link(settings, task_id)
    if link:
        await query.message.reply_text("\n".join(["Задача создана ✅", f"ID: {task_id}", f"Ссылка: {link}"]))
    else:
        await query.message.reply_text("\n".join(["Задача создана ✅", f"ID: {task_id}"]))

    context.user_data.clear()
    return ConversationHandler.END


# hydrate_link: оставляем, но делаем опору на sqlite через единый helper
async def hydrate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not getattr(update, "effective_user", None):
        return
    tg_id = int(update.effective_user.id)
    bid = get_linked_bitrix_id(context, tg_id)
    log.debug("HIT hydrate_link tg_id=%s linked=%s", tg_id, bid)

# =========================
# === CLEAN_LAYER_V1 ======
# =========================
# Этот блок intentionally переопределяет (exports) ключевые обработчики,
# чтобы устранить дубли/патчи выше по файлу и иметь однозначную архитектуру.

from linking import get_linked_bitrix_id as _get_linked_bitrix_id
from linking import set_linked_bitrix_id as _set_linked_bitrix_id

_CLEAN_LOG = logging.getLogger("clean")

# UX: /start -> 2 кнопки. HELP показываем только в экране "нужна привязка".
MAIN_MENU_START = ReplyKeyboardMarkup([[BTN_CREATE, BTN_LINK], [BTN_HELP]], resize_keyboard=True)
MAIN_MENU_LINK_REQUIRED = ReplyKeyboardMarkup([[BTN_CREATE, BTN_LINK], [BTN_HELP]], resize_keyboard=True)

async def show_link_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id if update.effective_user else None
    bid = _get_linked_bitrix_id(context, int(tg_id)) if tg_id else None
    _CLEAN_LOG.info("HIT show_link_required tg_id=%s linked=%s", tg_id, bid)
    await update.message.reply_text(
        "\n".join([
            "Сначала привяжите профиль Bitrix24 ✅",
            "Иначе задачи будут создаваться от технического пользователя.",
            "",
            "Нажмите «🔗 Привязать профиль» или «ℹ️ Как найти ID?»",
        ]),
        reply_markup=MAIN_MENU_LINK_REQUIRED
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    _CLEAN_LOG.info("HIT cmd_start tg_id=%s", update.effective_user.id)
    await update.message.reply_text("Выберите действие:", reply_markup=MAIN_MENU_START)

async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    bid = _get_linked_bitrix_id(context, tg_id)
    _CLEAN_LOG.info("HIT cmd_me tg_id=%s linked=%s", tg_id, bid)
    await update.message.reply_text(f"TG ID: {tg_id}\nBitrix ID (linked): {bid}", reply_markup=MAIN_MENU_START)

async def hydrate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # hydration остаётся, но source of truth — sqlite.
    try:
        if not getattr(update, "effective_user", None):
            return
        tg_id = int(update.effective_user.id)
    except Exception:
        return
    bid = _get_linked_bitrix_id(context, tg_id)
    if bid:
        try:
            context.user_data["bitrix_user_id"] = int(bid)
        except Exception:
            pass

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _CLEAN_LOG.info("HIT link_start tg_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "\n".join([
            "Привязать профиль Bitrix24:",
            "Пришлите ссылку на ваш профиль или просто число ID.",
            "",
            "Пример:",
            "https://fantasyclinic.bitrix24.ru/company/personal/user/123/",
            "или: 123",
        ]),
        reply_markup=MAIN_MENU_START
    )
    return LINK_WAIT

async def link_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.application.bot_data["settings"]
    tg_id = update.effective_user.id
    if not _is_allowed(settings, tg_id):
        await update.message.reply_text("Доступ запрещён.", reply_markup=MAIN_MENU_START)
        return ConversationHandler.END

    bitrix_user_id = parse_bitrix_user_id(update.message.text)
    if not bitrix_user_id:
        await update.message.reply_text(
            "Не понял ID. Пришлите ссылку вида .../user/123/ или просто число 123.",
            reply_markup=MAIN_MENU_START
        )
        return LINK_WAIT

    _set_linked_bitrix_id(context, tg_id, int(bitrix_user_id))
    _CLEAN_LOG.info("HIT link_receive tg_id=%s linked=%s", tg_id, bitrix_user_id)

    await update.message.reply_text(
        f"Готово ✅ Профиль привязан.\nТеперь нажмите «{BTN_CREATE}».",
        reply_markup=MAIN_MENU_START
    )
    return ConversationHandler.END

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id = update.effective_user.id
    bid = _get_linked_bitrix_id(context, tg_id)
    _CLEAN_LOG.info("HIT cmd_task tg_id=%s linked=%s text=%s", tg_id, bid, update.message.text if update.message else None)

    if not bid:
        await show_link_required(update, context)
        return ConversationHandler.END

    # дальше — оригинальная логика (создание тикета/состояния) как была
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, tg_id):
        await update.message.reply_text("Доступ запрещён.")
        return ConversationHandler.END

    context.user_data.clear()
    ticket_id = make_ticket_id()
    context.user_data["ticket_id"] = ticket_id
    context.user_data["files"] = []
    await update.message.reply_text("Ок. Введи *Название* задачи:", parse_mode="Markdown")
    return WAIT_TITLE

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # В main.py сейчас сюда попадает только HELP, но на всякий случай — держим полный роутер.
    text = (update.message.text or "").strip()
    tg_id = update.effective_user.id if update.effective_user else None
    bid = _get_linked_bitrix_id(context, int(tg_id)) if tg_id else None
    _CLEAN_LOG.info("HIT menu_router tg_id=%s linked=%s text=%s", tg_id, bid, text)

    if text == BTN_HELP:
        await help_find_id(update, context)
        return
    if text == BTN_LINK:
        await link_start(update, context)
        return
    if text == BTN_CREATE:
        # ВАЖНО: не вызывать cmd_task напрямую из меню в обход ConversationHandler.
        # Здесь просто подскажем нажать кнопку еще раз или /task — но у нас BTN_CREATE entry_point в ConversationHandler.
        # (Если вдруг сюда попадёт BTN_CREATE — значит main.py фильтр неверный.)
        await update.message.reply_text("Нажмите «📝 Создать задачу» ещё раз или используйте /task.", reply_markup=MAIN_MENU_START)
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU_START)

def build_conversation_handler() -> ConversationHandler:
    # ✅ BTN_CREATE как entry_point ConversationHandler (ключевой фикс)
    return ConversationHandler(
        entry_points=[
            CommandHandler("task", cmd_task),
            MessageHandler(filters.Regex(r"^📝 Создать задачу$"), cmd_task),
            CallbackQueryHandler(cb_start_task, pattern="^start_task$"),
        ],
        states={
            WAIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_title)],
            WAIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_description)],
            WAIT_ATTACHMENTS: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, on_attachment),
                CallbackQueryHandler(cb_attachments_done, pattern="^attachments_done$"),
                CallbackQueryHandler(cb_cancel_task, pattern="^cancel_task$"),
            ],
            CONFIRM: [
                CallbackQueryHandler(cb_confirm_create, pattern="^confirm_create$"),
                CallbackQueryHandler(cb_cancel_task, pattern="^cancel_task$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

def build_link_conversation_handler() -> ConversationHandler:
    # ✅ один хэндлер на BTN_LINK, без параллельных обработчиков
    return ConversationHandler(
        entry_points=[
            CommandHandler("link", link_start),
            MessageHandler(filters.Regex(r"^🔗 Привязать профиль$"), link_start),
        ],
        states={LINK_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_receive)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

# =========================
# === /CLEAN_LAYER_V1 =====
# =========================
