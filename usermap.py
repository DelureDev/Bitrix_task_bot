from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Optional
from utils import ensure_dir, now_iso


@dataclass
class UserMap:
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        ensure_dir(os.path.dirname(self.db_path) or ".")
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tg_bitrix_map (
                    tg_id INTEGER PRIMARY KEY,
                    bitrix_user_id INTEGER NOT NULL,
                    linked_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def set(self, tg_id: int, bitrix_user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tg_bitrix_map (tg_id, bitrix_user_id, linked_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tg_id) DO UPDATE SET
                    bitrix_user_id=excluded.bitrix_user_id,
                    linked_at=excluded.linked_at
                """,
                (tg_id, bitrix_user_id, now_iso()),
            )
            conn.commit()

    def get(self, tg_id: int) -> Optional[int]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT bitrix_user_id FROM tg_bitrix_map WHERE tg_id=?",
                (tg_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
