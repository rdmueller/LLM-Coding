"""Datenbankverbindung und Schema-Aufbau (ADR-0002, ADR-0004)."""
from __future__ import annotations

import sqlite3
from importlib import resources


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema = resources.files("app").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
