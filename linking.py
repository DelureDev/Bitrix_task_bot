from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

def get_linked_bitrix_id(context, tg_id: int) -> Optional[int]:
    """
    Single source of truth: читаем из sqlite через UserMap.
    Допускаем мягкий memory-cache в context.user_data["bitrix_user_id"].
    """
    try:
        # cache (не обязателен)
        ud = getattr(context, "user_data", None)
        if isinstance(ud, dict):
            cached = ud.get("bitrix_user_id")
            if isinstance(cached, int) and cached > 0:
                return cached
    except Exception:
        pass

    try:
        usermap = context.application.bot_data.get("usermap")
        if not usermap:
            return None
        bid = usermap.get(int(tg_id))
        if bid:
            try:
                if isinstance(getattr(context, "user_data", None), dict):
                    context.user_data["bitrix_user_id"] = int(bid)
            except Exception:
                pass
            return int(bid)
        return None
    except Exception:
        log.exception("get_linked_bitrix_id failed tg_id=%s", tg_id)
        return None


def set_linked_bitrix_id(context, tg_id: int, bitrix_user_id: int) -> None:
    """Запись только в sqlite (UserMap), затем обновляем cache."""
    usermap = context.application.bot_data["usermap"]
    usermap.set(int(tg_id), int(bitrix_user_id))
    try:
        if isinstance(getattr(context, "user_data", None), dict):
            context.user_data["bitrix_user_id"] = int(bitrix_user_id)
    except Exception:
        pass
