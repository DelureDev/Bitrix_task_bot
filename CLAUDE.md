# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Telegram bot that creates tasks in Bitrix24. Users link their Bitrix profile once via `/link`, then use `/task` to submit tasks with optional file attachments. Files are saved locally and synced to Bitrix Disk before task creation.

## Running the Bot

```bash
# Set up virtualenv (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run
python main.py
```

No test suite exists. Debugging is done via `LOG_LEVEL=DEBUG` in `.env`.

## Required `.env` Variables

| Variable | Notes |
|----------|-------|
| `TG_BOT_TOKEN` | Required |
| `BITRIX_WEBHOOK_BASE` | Required; **must end with `/`** |
| `BITRIX_DEFAULT_RESPONSIBLE_ID` | Required; integer Bitrix user ID |
| `BITRIX_DISK_FOLDER_ID` | Required; integer folder ID in Bitrix Disk |
| `ALLOWED_TG_USERS` | CSV of Telegram user IDs; empty = all allowed |
| `UPLOAD_DIR` | Default: `./uploads` |
| `USERMAP_DB` | Default: `./data/users.db` |
| `BITRIX_PORTAL_BASE` | Optional; base URL for portal links |
| `BITRIX_TASK_URL_TEMPLATE` | Optional; URL template for task links |
| `BITRIX_GROUP_ID` | Optional; Bitrix workgroup/project ID |
| `BITRIX_PRIORITY` | Optional; task priority integer |
| `ENABLE_MYTASKS` | Default: `true`; enables `/mytasks` command |
| `LOG_LEVEL` | Default: `INFO` |

## Module Architecture

| Module | Role |
|--------|------|
| `main.py` | Entry point: loads settings, initializes `BitrixClient` and `UserMap`, registers all handlers into `app.bot_data` |
| `bot_handlers.py` | All Telegram conversation handlers (state machines), keyboard layouts, message formatting, `/mytasks` display |
| `bitrix.py` | `BitrixClient`: async HTTP client wrapping Bitrix24 REST webhook; task creation and dual-strategy file upload |
| `config.py` | `load_settings()` → frozen `Settings` dataclass; validates all env vars at startup |
| `usermap.py` | SQLite persistence: `tg_bitrix_map(tg_id, bitrix_user_id, linked_at)` |
| `linking.py` | Helper layer with soft cache via `context.user_data["bitrix_user_id"]`; reads UserMap as source of truth |
| `storage.py` | Builds local file paths: `UPLOAD_DIR/YYYY-MM-DD/<tg_id>/<ticket_id>/` |
| `utils.py` | `make_ticket_id()`, `safe_filename()`, `ensure_dir()` |

## Shared State via `bot_data`

All handlers access shared objects through `context.application.bot_data`:

```python
context.application.bot_data["settings"]  # Settings dataclass
context.application.bot_data["bitrix"]    # BitrixClient instance
context.application.bot_data["usermap"]   # UserMap instance
context.user_data                          # Per-user session dict (lost on restart)
```

## Conversation State Machine

`/task` flow states (defined in `bot_handlers.py`):
```python
WAIT_TITLE, WAIT_DESCRIPTION, WAIT_ATTACHMENTS, CONFIRM = range(4)
LINK_WAIT = 9901  # separate /link conversation
```

Handler groups in `main.py`:
- Group `-1`: `hydrate_link` — pre-fills `context.user_data["bitrix_user_id"]` from SQLite before every message
- Group `0`: menu button routers
- Group `1`: `ConversationHandler` instances for `/task` and `/link`
- Group `99`: fallback `maybe_show_menu`

## Bitrix File Upload Strategy

`BitrixClient.upload_file_sync()` tries two methods in order:
1. **`fileContent`** — base64-encoded body (fast, limited size)
2. **`uploadUrl`** — signed URL upload (fallback for larger files)

File IDs are passed to tasks as `UF_TASK_WEBDAV_FILES=["n<id>", ...]` (the `n` prefix denotes WebDAV object type).

## Access Control

`ALLOWED_TG_USERS` is checked via `_is_allowed(settings, tg_user_id)` before every user action. If denied, reply "Доступ запрещён." and return `ConversationHandler.END`.

## Task Creation Fallback

Task creation first tries with `CREATED_BY=<linked_bitrix_user_id>`. If Bitrix rejects it, it retries without `CREATED_BY` (task is owned by the webhook user instead).

## Common Errors

| Error | Cause |
|-------|-------|
| `BitrixError: HTTP 401` | Webhook token expired; regenerate in Bitrix portal |
| `Cannot parse disk file id` | `BITRIX_DISK_FOLDER_ID` wrong or inaccessible |
| `CREATED_BY=N rejected` | Linked Bitrix user ID doesn't match actual portal user |
