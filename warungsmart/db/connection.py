from __future__ import annotations

import sqlite3
from pathlib import Path

from warungsmart import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_conn() -> sqlite3.Connection:
    path = Path(config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
