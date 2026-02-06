from __future__ import annotations

import datetime as dt
import os
import re
import uuid


def now_iso() -> str:
    # Use local time on server
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def make_ticket_id() -> str:
    return uuid.uuid4().hex[:10]


def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\.-]+", "_", name)
    name = name.strip("._")
    if not name:
        return "file"
    return name[:120]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
