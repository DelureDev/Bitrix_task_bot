# Copilot Instructions - Bitrix Task Bot

A Telegram bot that creates tasks in Bitrix24. Users link their Bitrix profile once, then use conversation handlers to submit tasks with optional file attachments, which are synced to Bitrix Disk before task creation.

## Architecture Overview

### Component Boundaries

| Module | Purpose |
|--------|---------|
| **main.py** | Application entry point; initializes `app.bot_data` with settings, BitrixClient, and UserMap; registers all handlers. |
| **bot_handlers.py** | Telegram conversation handlers (state machines) for `/task` and `/link` commands; keyboard layouts and message formatting. |
| **bitrix.py** | HTTP client wrapping Bitrix24 REST webhook; handles task creation, file uploads with dual strategies (fileContent + uploadUrl fallback). |
| **config.py** | Loads and validates .env variables; raises RuntimeError if required settings missing (e.g., webhook URL must end with `/`). |
| **usermap.py** | SQLite persistence for tg_id → bitrix_user_id mappings; table `tg_bitrix_map(tg_id, bitrix_user_id, linked_at)`. |
| **linking.py** | Helper layer with soft memory caching via `context.user_data["bitrix_user_id"]`; reads from usermap as single source of truth. |
| **storage.py** | Builds directory paths for local file uploads: `UPLOAD_DIR/YYYY-MM-DD/<tg_id>/<ticket_id>/`. |
| **utils.py** | Utility functions: ticket ID generation, safe filename sanitization. |

### Data Flow: Task Creation

```
User /task
  ↓
WAIT_TITLE (get title)
  ↓
WAIT_DESCRIPTION (get description)
  ↓
WAIT_ATTACHMENTS (save files locally)
  ↓
CONFIRM (show preview, callback: confirm_create)
  ↓
Upload files to Bitrix Disk → get file IDs
  ↓
Create task in Bitrix with UF_TASK_WEBDAV_FILES=[n<file_id>, ...]
  ↓
Return task ID + link
```

### Data Flow: User Linking

```
User /link
  ↓
LINK_WAIT (parse URL or raw ID)
  ↓
UserMap.set(tg_id, bitrix_user_id) → SQLite
  ↓
Cache in context.user_data["bitrix_user_id"]
```

## Critical Patterns

### Access Control
- **ALLOWED_TG_USERS**: CSV list in .env; empty = all users allowed
- Checked via `_is_allowed(settings, tg_user_id)` **before every user action**
- If disallowed, reply "Доступ запрещён." and return `ConversationHandler.END`

### Conversation State Machine
States defined as integers:
```python
WAIT_TITLE, WAIT_DESCRIPTION, WAIT_ATTACHMENTS, CONFIRM = range(4)
LINK_WAIT = 9901  # Link conversation uses separate state
```
- Use `ConversationHandler` with `entry_points`, `states` dict, and `fallbacks` list
- Handlers return next state (int) or `ConversationHandler.END`
- User state data stored in `context.user_data` dict (lost on bot restart)

### Bitrix Integration
- **Client**: `context.application.bot_data["bitrix"]` (initialized in main.py)
- **Methods**: `call(method, data)` for generic REST; `upload_file_sync(folder_id, path, name)` for disk uploads
- **Error Handling**: Raises `BitrixError(message, details)` on HTTP errors or malformed responses
- **Upload Strategy**:
  1. Try `fileContent` (base64 encoding, fast path)
  2. Fall back to `uploadUrl` if step 1 fails (signed URL, supports larger files)
  3. Both return file ID needed for task creation

### User-Bitrix Mapping
- **Single source of truth**: `UserMap` (SQLite)
- **Soft cache**: `context.user_data.get("bitrix_user_id")` (optional, improves UX)
- **Fetching**: Use `linking.get_linked_bitrix_id(context, tg_id)` (handles cache + DB fallback)
- **Writing**: Use `linking.set_linked_bitrix_id(context, tg_id, bitrix_user_id)` (writes DB + updates cache)

### File Upload Workflow
1. **Local Save**: `build_upload_dir()` creates `UPLOAD_DIR/YYYY-MM-DD/<tg_id>/<ticket_id>/` and saves files
2. **Disk Upload**: Loop through SavedFile objects, upload to Bitrix Disk folder (BITRIX_DISK_FOLDER_ID)
3. **Partial Failures**: If any file fails to upload and user attached files → show error list, **don't create task**
4. **Partial Success**: If some files uploaded successfully → create task with available file IDs, show failed list

### Required Validation
Before task creation, enforce:
- ✅ User has linked Bitrix profile (check `get_linked_bitrix_id()`)
- ✅ Title is non-empty
- ✅ If files attached, at least one must upload successfully to Bitrix Disk
- ❌ No fallback task creation if core requirements fail

## Important Implementation Details

### Fallback in Task Creation
- **Primary**: Create with `CREATED_BY=<linked_bitrix_user_id>`
- **Fallback**: If Bitrix rejects CREATED_BY, retry without it (responsibility falls to webhook user)

### Task Description Structure
```python
build_task_description(user_desc, initiator_block, attachments_block)
# initiator_block = "Контакт инициатора:\nTelegram: @username"
# attachments_block = "" (intentionally blank to avoid local path clutter)
```

### File Attachment Representation in Bitrix
- Task field: `UF_TASK_WEBDAV_FILES` (array of file references)
- Format: `[f"n{file_id}" for file_id in uploaded_file_ids]`
- Prefix `n` indicates WebDAV file object type

### Configuration Validation
Startup checks in `config.py`:
- `TG_BOT_TOKEN`: required, non-empty
- `BITRIX_WEBHOOK_BASE`: required, **must end with `/`** (validated explicitly)
- `BITRIX_DEFAULT_RESPONSIBLE_ID`: required, integer
- `BITRIX_DISK_FOLDER_ID`: required, integer (folder in Bitrix Disk for uploads)
- Defaults: `UPLOAD_DIR=./uploads`, `USERMAP_DB=./data/users.db`, `LOG_LEVEL=INFO`

## Common Modification Points & Patterns

### Adding a New Command
1. Create async handler: `async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:`
2. Register in main.py: `app.add_handler(CommandHandler("new", cmd_new))`
3. Use `context.application.bot_data["settings"]` for config access

### Extending Conversation Handler
1. Add state constant (e.g., `NEW_STATE = 5`)
2. Create handler function returning new state or `ConversationHandler.END`
3. Update `states` dict in `ConversationHandler(states={..})`

### Accessing Shared Data in Handlers
- Settings: `context.application.bot_data["settings"]`
- Bitrix client: `context.application.bot_data["bitrix"]`
- User-Bitrix map: `context.application.bot_data["usermap"]`
- User session data: `context.user_data` (dict, lost on restart)

### Logging
- Import: `import logging; log = logging.getLogger(__name__)`
- Level controlled by `LOG_LEVEL` env var (default: INFO)
- Log early task state transitions and API calls for debugging

## Testing & Debugging

### Local Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # python-telegram-bot, httpx, python-dotenv
```

### Required .env Values for Testing
```
TG_BOT_TOKEN=<your_telegram_bot_token>
BITRIX_WEBHOOK_BASE=https://yourportal.bitrix24.ru/rest/1/abcdef/
BITRIX_DEFAULT_RESPONSIBLE_ID=1
BITRIX_DISK_FOLDER_ID=<folder_id>
ALLOWED_TG_USERS=<your_tg_id>
LOG_LEVEL=DEBUG  # verbose logging
```

### Run Bot
```powershell
python main.py
```

### Common Errors & Checks
| Error | Check |
|-------|-------|
| `BitrixError: ... HTTP 401` | Webhook token expired or invalid; regenerate in Bitrix portal |
| `Cannot parse disk file id` | `BITRIX_DISK_FOLDER_ID` wrong or inaccessible to webhook user |
| `CREATED_BY=N rejected` | Bitrix user ID mismatch; verify linked profile matches actual user in portal |
| Files upload slowly | Check REST API rate limits; default timeouts: 20s (normal), 90s (upload), 25s (upload URL) |
