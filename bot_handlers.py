from __future__ import annotations

import asyncio
import datetime
import logging
import os
import re
from typing import List

import httpx
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
from linking import get_linked_bitrix_id as _get_linked_bitrix_id
from linking import set_linked_bitrix_id as _set_linked_bitrix_id
from storage import build_upload_dir, make_local_path, SavedFile
from utils import make_ticket_id, safe_filename

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Button labels
# ---------------------------------------------------------------------------
BTN_CREATE = "📝 Создать задачу"
BTN_LINK = "🔗 Привязать профиль"
BTN_HELP = "ℹ️ Как найти ID?"
BTN_MY_TASKS = "📋 Мои задачи"

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------
WAIT_TITLE, WAIT_DESCRIPTION, WAIT_ATTACHMENTS, CONFIRM = range(4)
LINK_WAIT = 9901

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
MAX_ATTACHMENTS_PER_TASK = 10
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB
UPLOAD_PARALLELISM = 2
MYTASKS_LIMIT = 5

# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------
MAIN_MENU_START = ReplyKeyboardMarkup(
    [[BTN_CREATE, BTN_LINK], [BTN_MY_TASKS, BTN_HELP]],
    resize_keyboard=True,
)
MAIN_MENU_LINK_REQUIRED = ReplyKeyboardMarkup(
    [[BTN_CREATE, BTN_LINK], [BTN_MY_TASKS, BTN_HELP]],
    resize_keyboard=True,
)

# ---------------------------------------------------------------------------
# Task status labels
# ---------------------------------------------------------------------------
_REAL_STATUS_LABELS = {
    1: "Новая",
    2: "Ждёт выполнения",
    3: "В работе",
    4: "Ждёт контроля",
    5: "Завершена",
    6: "Отложена",
    7: "Отклонена",
}

# ---------------------------------------------------------------------------
# Inline keyboard builders
# ---------------------------------------------------------------------------

def _kb_attachments() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Готово ✅", callback_data="attachments_done")],
            [InlineKeyboardButton("Отмена ❌", callback_data="cancel_task")],
        ]
    )


def _kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Создать ✅", callback_data="confirm_create")],
            [InlineKeyboardButton("Отмена ❌", callback_data="cancel_task")],
        ]
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def parse_bitrix_user_id(text: str) -> int | None:
    t = (text or "").strip()
    if t.isdigit():
        return int(t)
    m = re.search(r"/user/(\d+)/", t)
    if m:
        return int(m.group(1))
    m = re.search(r"user/(\d+)", t)
    if m:
        return int(m.group(1))
    return None


def _attachment_too_large(size_bytes: int | None) -> bool:
    if not size_bytes:
        return False
    return int(size_bytes) > MAX_ATTACHMENT_BYTES


def _is_allowed(settings: Settings, tg_user_id: int) -> bool:
    if not settings.allowed_tg_users:
        return True
    return tg_user_id in settings.allowed_tg_users


def _task_link(settings: Settings, task_id: int) -> str:
    tpl = (settings.bitrix_task_url_template or "").strip()
    if tpl:
        return tpl.format(task_id=task_id)
    base = (settings.bitrix_portal_base or "").strip().rstrip("/")
    if base:
        rid = settings.bitrix_default_responsible_id
        return f"{base}/company/personal/user/{rid}/tasks/task/view/{task_id}/"
    return ""


def _saved_file_label(saved_file: SavedFile) -> str:
    name = (saved_file.original_name or "").strip()
    if name:
        return name
    return os.path.basename(saved_file.local_path) or "file"


def _is_retryable_upload_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, BitrixError):
        details = f"{exc.message} {exc.details}".lower()
        markers = (
            "timeout",
            "readtimeout",
            "connecttimeout",
            "remoteprotocolerror",
            "all disk upload strategies failed",
            "temporar",
            "service unavailable",
            "gateway timeout",
            "too many request",
            "internal",
            "network",
            "502",
            "503",
            "504",
        )
        return any(marker in details for marker in markers)
    return False


def _format_exception_brief(exc: Exception) -> str:
    if isinstance(exc, BitrixError):
        text = (exc.message or "").strip()
    else:
        text = str(exc).strip()
    if text:
        return f"{exc.__class__.__name__}: {text}"
    return exc.__class__.__name__


def build_task_description(user_desc: str, initiator_block: str, attachments_block: str) -> str:
    parts = [user_desc.strip(), "", initiator_block.strip()]
    attachments_block = (attachments_block or "").strip()
    if attachments_block:
        parts.extend(["", attachments_block])
    return "\n".join(parts).strip()


def build_initiator_block(update: Update) -> str:
    u = update.effective_user
    username = f"@{u.username}" if (u and u.username) else ""
    if not username:
        username = f"tg_id:{u.id}" if u else "-"
    return "Контакт инициатора:\nTelegram: " + username


def build_attachments_block(files: List[SavedFile], upload_root: str) -> str:
    # Local file paths are internal; keep Bitrix task description clean.
    return ""


# ---------------------------------------------------------------------------
# Task list helpers
# ---------------------------------------------------------------------------

def _status_label(task: dict) -> str:
    raw = task.get("realStatus", task.get("REAL_STATUS", task.get("status", task.get("STATUS"))))
    if isinstance(raw, dict):
        for key in ("name", "NAME", "title", "TITLE", "value", "VALUE"):
            val = raw.get(key)
            if val:
                return str(val)
        raw = raw.get("id", raw.get("ID"))
    try:
        return _REAL_STATUS_LABELS.get(int(raw), str(int(raw)))
    except Exception:
        return str(raw or "-")


def _deadline_label(task: dict) -> str:
    deadline = task.get("deadline", task.get("DEADLINE"))
    if not deadline:
        return "-"
    text = str(deadline).strip()
    if not text:
        return "-"
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(normalized)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return text


def _task_id(task: dict) -> int | None:
    raw = task.get("id", task.get("ID"))
    try:
        return int(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Common handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.application.bot_data["settings"]
    if not _is_allowed(settings, update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    log.info("HIT cmd_start tg_id=%s", update.effective_user.id)
    await update.message.reply_text("Выберите действие:", reply_markup=MAIN_MENU_START)


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    bid = _get_linked_bitrix_id(context, tg_id)
    log.info("HIT cmd_me tg_id=%s linked=%s", tg_id, bid)
    await update.message.reply_text(
        f"TG ID: {tg_id}\nBitrix ID (linked): {bid}",
        reply_markup=MAIN_MENU_START,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Отменено.", reply_markup=MAIN_MENU_START)
    return ConversationHandler.END


async def help_find_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "\n".join([
            "Как найти ID в Bitrix24:",
            "1) Откройте Bitrix24: https://<portal>.bitrix24.ru/",
            "2) Нажмите на своё имя/аватар → Профиль",
            "3) В адресной строке будет .../company/personal/user/123/ — число 123 и есть ваш ID",
            "",
            "Можно прислать ссылку целиком или просто число.",
        ]),
        reply_markup=MAIN_MENU_START,
    )


async def show_link_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id if update.effective_user else None
    bid = _get_linked_bitrix_id(context, int(tg_id)) if tg_id else None
    log.info("HIT show_link_required tg_id=%s linked=%s", tg_id, bid)
    await update.message.reply_text(
        "\n".join([
            "Сначала привяжите профиль Bitrix24 ✅",
            "Иначе задачи будут создаваться от технического пользователя.",
            "",
            "Нажмите «🔗 Привязать профиль» или «ℹ️ Как найти ID?»",
        ]),
        reply_markup=MAIN_MENU_LINK_REQUIRED,
    )


async def maybe_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the main menu once (first message in chat), without spamming."""
    try:
        if context.user_data.get("_menu_shown"):
            return
        context.user_data["_menu_shown"] = True
    except Exception:
        return

    txt = (getattr(getattr(update, "message", None), "text", None) or "").strip()
    if txt in (BTN_CREATE, BTN_LINK, BTN_HELP, BTN_MY_TASKS):
        return

    await cmd_start(update, context)


async def cmd_mytasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["_menu_shown"] = True
    settings = context.application.bot_data["settings"]
    tg_id = update.effective_user.id
    if not _is_allowed(settings, tg_id):
        await update.message.reply_text("Доступ запрещён.", reply_markup=MAIN_MENU_START)
        return

    if not getattr(settings, "enable_mytasks", True):
        await update.message.reply_text(
            "Функция «Мои задачи» сейчас отключена администратором.",
            reply_markup=MAIN_MENU_START,
        )
        return

    bitrix_user_id = _get_linked_bitrix_id(context, tg_id)
    log.info("HIT cmd_mytasks tg_id=%s linked=%s", tg_id, bitrix_user_id)
    if not bitrix_user_id:
        await show_link_required(update, context)
        return

    bitrix: BitrixClient = context.application.bot_data["bitrix"]
    await update.message.reply_text("Смотрю задачи, которые вы создали в Bitrix24…")
    try:
        tasks = await bitrix.list_tasks_created_by(int(bitrix_user_id), limit=MYTASKS_LIMIT)
    except Exception:
        log.exception("cmd_mytasks failed tg_id=%s bitrix_user_id=%s", tg_id, bitrix_user_id)
        await update.message.reply_text(
            "Не удалось получить список задач из Bitrix24. Попробуйте позже.",
            reply_markup=MAIN_MENU_START,
        )
        return

    if not tasks:
        await update.message.reply_text(
            "Задач, созданных вами, пока нет ✅",
            reply_markup=MAIN_MENU_START,
        )
        return

    lines = ["📋 Ваши последние задачи (вы автор):"]
    for index, task in enumerate(tasks, start=1):
        tid = _task_id(task)
        title = str(task.get("title", task.get("TITLE", "(без названия)"))).strip() or "(без названия)"
        if len(title) > 110:
            title = f"{title[:107]}..."
        status = _status_label(task)
        deadline = _deadline_label(task)
        row = [f"{index}. #{tid if tid is not None else '?'} — {title}", f"Статус: {status}"]
        if deadline != "-":
            row.append(f"Срок: {deadline}")
        if tid is not None:
            link = _task_link(settings, tid)
            if link:
                row.append(f"Ссылка: {link}")
        lines.append("\n".join(row))

    await update.message.reply_text("\n\n".join(lines), reply_markup=MAIN_MENU_START)


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    tg_id = update.effective_user.id if update.effective_user else None
    bid = _get_linked_bitrix_id(context, int(tg_id)) if tg_id else None
    log.info("HIT menu_router tg_id=%s linked=%s", tg_id, bid)

    if text == BTN_HELP:
        await help_find_id(update, context)
        return
    if text == BTN_MY_TASKS:
        await cmd_mytasks(update, context)
        return
    if text == BTN_LINK:
        await link_start(update, context)
        return
    if text == BTN_CREATE:
        # BTN_CREATE is an entry_point in the task ConversationHandler.
        # If we reach this router, the ConversationHandler didn't catch it — prompt again.
        await update.message.reply_text(
            "Нажмите «📝 Создать задачу» ещё раз или используйте /task.",
            reply_markup=MAIN_MENU_START,
        )
        return

    await update.message.reply_text("Выберите действие кнопкой 👇", reply_markup=MAIN_MENU_START)


async def hydrate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


# ---------------------------------------------------------------------------
# /link conversation
# ---------------------------------------------------------------------------

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    log.info("HIT link_start tg_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "\n".join([
            "Привязать профиль Bitrix24:",
            "Пришлите ссылку на ваш профиль или просто число ID.",
            "",
            "Пример:",
            "https://<portal>.bitrix24.ru/company/personal/user/123/",
            "или: 123",
        ]),
        reply_markup=MAIN_MENU_START,
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
            reply_markup=MAIN_MENU_START,
        )
        return LINK_WAIT

    _set_linked_bitrix_id(context, tg_id, int(bitrix_user_id))
    log.info("HIT link_receive tg_id=%s linked=%s", tg_id, bitrix_user_id)
    await update.message.reply_text(
        f"Готово ✅ Профиль привязан.\nТеперь нажмите «{BTN_CREATE}».",
        reply_markup=MAIN_MENU_START,
    )
    return ConversationHandler.END


def build_link_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("link", link_start),
            MessageHandler(filters.Regex(r"^🔗 Привязать профиль$"), link_start),
        ],
        states={LINK_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_receive)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )


# ---------------------------------------------------------------------------
# /task conversation
# ---------------------------------------------------------------------------

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id = update.effective_user.id
    bid = _get_linked_bitrix_id(context, tg_id)
    log.info("HIT cmd_task tg_id=%s linked=%s", tg_id, bid)

    if not bid:
        await show_link_required(update, context)
        return ConversationHandler.END

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


async def cb_start_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
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
    await update.message.reply_text(
        "Теперь введи *Описание* (что сделать/что не работает/контекст):",
        parse_mode="Markdown",
    )
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
    if len(saved) >= MAX_ATTACHMENTS_PER_TASK:
        await update.message.reply_text(
            f"Лимит вложений: {MAX_ATTACHMENTS_PER_TASK} на одну задачу. Нажмите «Готово ✅»."
        )
        return WAIT_ATTACHMENTS

    if update.message.photo:
        photo = update.message.photo[-1]
        if _attachment_too_large(getattr(photo, "file_size", None)):
            await update.message.reply_text(
                "Файл слишком большой. Максимальный размер вложения: 20 MB."
            )
            return WAIT_ATTACHMENTS
        file = await context.bot.get_file(photo.file_id)
        filename = f"photo_{photo.file_unique_id}.jpg"
        local_path = make_local_path(upload_dir, filename)
        await file.download_to_drive(custom_path=local_path)
        saved.append(SavedFile(original_name=filename, local_path=local_path))
        context.user_data["files"] = saved
        await update.message.reply_text(f"Ок, сохранил фото: {filename}")
        return WAIT_ATTACHMENTS

    if update.message.document:
        doc = update.message.document
        if _attachment_too_large(getattr(doc, "file_size", None)):
            await update.message.reply_text(
                "Файл слишком большой. Максимальный размер вложения: 20 MB."
            )
            return WAIT_ATTACHMENTS
        file = await context.bot.get_file(doc.file_id)
        original = doc.file_name or f"document_{doc.file_unique_id}"
        filename = safe_filename(original)
        local_path = make_local_path(upload_dir, filename)
        await file.download_to_drive(custom_path=local_path)
        saved.append(SavedFile(original_name=original, local_path=local_path))
        context.user_data["files"] = saved
        await update.message.reply_text(f"Ок, сохранил файл: {original}")
        return WAIT_ATTACHMENTS

    await update.message.reply_text(
        "Я могу принять фото или документ. Пришли файл/скриншот или нажми Готово ✅."
    )
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
    await query.message.reply_text("Отменено.", reply_markup=MAIN_MENU_START)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# File upload to Bitrix Disk
# ---------------------------------------------------------------------------

async def _upload_files_to_bitrix_disk(
    bitrix: BitrixClient,
    folder_id: int,
    files: List[SavedFile],
    max_attempts: int = 2,
    upload_parallelism: int = UPLOAD_PARALLELISM,
) -> tuple[list[int], list[str]]:
    if not files:
        return [], []

    semaphore = asyncio.Semaphore(max(1, min(upload_parallelism, len(files))))

    async def _upload_one(saved_file: SavedFile) -> tuple[int | None, str | None]:
        file_label = _saved_file_label(saved_file)
        async with semaphore:
            for attempt in range(1, max_attempts + 1):
                log.info(
                    "Disk upload start name=%s attempt=%s/%s folder_id=%s",
                    file_label, attempt, max_attempts, folder_id,
                )
                try:
                    file_id = await bitrix.upload_to_folder(
                        folder_id=folder_id,
                        local_path=saved_file.local_path,
                        filename=file_label,
                        upload_attempt=attempt,
                        upload_max_attempts=max_attempts,
                    )
                    log.info(
                        "Disk upload success name=%s file_id=%s attempt=%s/%s",
                        file_label, file_id, attempt, max_attempts,
                    )
                    return int(file_id), None
                except Exception as exc:
                    retryable = attempt < max_attempts and _is_retryable_upload_error(exc)
                    if retryable:
                        log.warning(
                            "Disk upload retry name=%s attempt=%s/%s error=%s",
                            file_label, attempt, max_attempts, _format_exception_brief(exc),
                        )
                        continue
                    log.exception(
                        "Disk upload failed name=%s attempt=%s/%s error=%s",
                        file_label, attempt, max_attempts, _format_exception_brief(exc),
                    )
                    return None, file_label
            return None, file_label

    results = await asyncio.gather(*(_upload_one(saved_file) for saved_file in files))

    uploaded_ids: list[int] = []
    failed_files: list[str] = []
    for file_id, failed in results:
        if file_id is not None:
            uploaded_ids.append(file_id)
        if failed:
            failed_files.append(failed)

    return uploaded_ids, failed_files


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

    created_by = _get_linked_bitrix_id(context, update.effective_user.id)
    log.info("HIT cb_confirm_create tg_id=%s created_by=%s", update.effective_user.id, created_by)

    if created_by is None:
        await query.message.reply_text(
            "Нельзя создать задачу без привязки профиля Bitrix24.\n"
            "Сначала нажмите «🔗 Привязать профиль» и пришлите ID/ссылку."
        )
        context.user_data.clear()
        return ConversationHandler.END

    uploaded_ids: list[int] = []
    failed_files: list[str] = []
    if files:
        await query.message.reply_text(f"Загружаю вложения в Bitrix24 Disk: {len(files)} шт.")
        uploaded_ids, failed_files = await _upload_files_to_bitrix_disk(
            bitrix=bitrix,
            folder_id=settings.bitrix_disk_folder_id,
            files=files,
            max_attempts=settings.bitrix_upload_max_attempts,
            upload_parallelism=settings.bitrix_upload_parallelism,
        )
        if failed_files and not uploaded_ids:
            failed_list = "\n".join(f"- {name}" for name in failed_files)
            await query.message.reply_text(
                "Не удалось загрузить ни одно вложение, задача не создана.\n"
                "Проверьте доступ к папке Bitrix Disk и попробуйте снова.\n\n"
                f"Неуспешные файлы:\n{failed_list}"
            )
            context.user_data.clear()
            return ConversationHandler.END
        if failed_files:
            failed_list = "\n".join(f"- {name}" for name in failed_files)
            await query.message.reply_text(
                "Часть вложений не загрузилась. Создам задачу только с успешно загруженными файлами.\n\n"
                f"Неуспешные файлы:\n{failed_list}"
            )

    await query.message.reply_text("Создаю задачу в Bitrix24…")

    try:
        task_id = await bitrix.create_task(
            title=title,
            description=full_desc,
            responsible_id=settings.bitrix_default_responsible_id,
            group_id=settings.bitrix_group_id,
            priority=settings.bitrix_priority,
            created_by=created_by,
            webdav_file_ids=uploaded_ids,
        )
    except BitrixError as e:
        log.warning("Bitrix rejected CREATED_BY=%s, retrying without it: %s", created_by, e.message)
        try:
            task_id = await bitrix.create_task(
                title=title,
                description=full_desc,
                responsible_id=settings.bitrix_default_responsible_id,
                group_id=settings.bitrix_group_id,
                priority=settings.bitrix_priority,
                created_by=None,
                webdav_file_ids=uploaded_ids,
            )
        except Exception:
            log.exception("Bitrix error (retry without CREATED_BY)")
            await query.message.reply_text(
                "Не получилось создать задачу из-за ошибки Bitrix24. Попробуйте позже."
            )
            context.user_data.clear()
            return ConversationHandler.END
    except Exception:
        log.exception("Unexpected error")
        await query.message.reply_text(
            "Не получилось создать задачу из-за ошибки Bitrix24. Попробуйте позже."
        )
        context.user_data.clear()
        return ConversationHandler.END

    link = _task_link(settings, task_id)
    result_lines = ["Задача создана ✅", f"ID: {task_id}"]
    if link:
        result_lines.append(f"Ссылка: {link}")
    if uploaded_ids:
        result_lines.append(f"Вложений прикреплено: {len(uploaded_ids)}")
    if failed_files:
        failed_list = "\n".join(f"- {name}" for name in failed_files)
        result_lines.append("Не загрузились файлы:\n" + failed_list)
    await query.message.reply_text("\n".join(result_lines), reply_markup=MAIN_MENU_START)

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
