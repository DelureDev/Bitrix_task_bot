from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from utils import ensure_dir, safe_filename


@dataclass
class SavedFile:
    original_name: str
    local_path: str


def build_upload_dir(base_dir: str, date_str: str, tg_user_id: int, ticket_id: str) -> str:
    path = os.path.join(base_dir, date_str, str(tg_user_id), ticket_id)
    ensure_dir(path)
    return path


def make_local_path(upload_dir: str, filename: str) -> str:
    filename = safe_filename(filename)
    return os.path.join(upload_dir, filename)
