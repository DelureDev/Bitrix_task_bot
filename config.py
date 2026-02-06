from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _getenv(name: str, default: str = "") -> str:
    val = os.getenv(name, default).strip()
    return val


def _getenv_int(name: str, default: int | None = None) -> int | None:
    val = _getenv(name)
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"Env {name} must be integer, got: {val}")


def _parse_csv_ints(s: str) -> set[int]:
    s = (s or "").strip()
    if not s:
        return set()
    out = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return out


@dataclass(frozen=True)
class Settings:
    tg_bot_token: str
    bitrix_webhook_base: str
    bitrix_default_responsible_id: int
    bitrix_group_id: int | None
    bitrix_priority: int | None
    bitrix_portal_base: str
    bitrix_task_url_template: str
    allowed_tg_users: set[int]
    upload_dir: str
    usermap_db: str
    log_level: str


def load_settings() -> Settings:
    tg_bot_token = _getenv("TG_BOT_TOKEN")
    if not tg_bot_token:
        raise RuntimeError("TG_BOT_TOKEN is required")

    bitrix_webhook_base = _getenv("BITRIX_WEBHOOK_BASE")
    if not bitrix_webhook_base:
        raise RuntimeError("BITRIX_WEBHOOK_BASE is required")
    if not bitrix_webhook_base.endswith("/"):
        raise RuntimeError("BITRIX_WEBHOOK_BASE must end with '/'")

    resp_id = _getenv_int("BITRIX_DEFAULT_RESPONSIBLE_ID")
    if resp_id is None:
        raise RuntimeError("BITRIX_DEFAULT_RESPONSIBLE_ID is required")

    group_id = _getenv_int("BITRIX_GROUP_ID", None)
    priority = _getenv_int("BITRIX_PRIORITY", None)

    portal_base = _getenv("BITRIX_PORTAL_BASE")
    task_url_tpl = _getenv("BITRIX_TASK_URL_TEMPLATE")

    allowed = _parse_csv_ints(_getenv("ALLOWED_TG_USERS"))

    upload_dir = _getenv("UPLOAD_DIR", "./uploads")
    usermap_db = _getenv("USERMAP_DB", "./data/users.db")
    log_level = _getenv("LOG_LEVEL", "INFO").upper()

    return Settings(
        tg_bot_token=tg_bot_token,
        bitrix_webhook_base=bitrix_webhook_base,
        bitrix_default_responsible_id=resp_id,
        bitrix_group_id=group_id,
        bitrix_priority=priority,
        bitrix_portal_base=portal_base,
        bitrix_task_url_template=task_url_tpl,
        allowed_tg_users=allowed,
        upload_dir=upload_dir,
        usermap_db=usermap_db,
        log_level=log_level,
    )
