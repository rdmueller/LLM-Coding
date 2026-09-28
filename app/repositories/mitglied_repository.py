"""Repository für Mitglied."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Mitglied
from app.repositories._transaction import commit_when_unmanaged


class MitgliedRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(self, name: str) -> Mitglied:
        mitglied_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO mitglied (id, name, gesperrt) VALUES (?, ?, 0)",
            (mitglied_id, name),
        )
        commit_when_unmanaged(self._conn)
        return Mitglied(id=mitglied_id, name=name, gesperrt=False)

    def finden(self, mitglied_id: str) -> Mitglied | None:
        row = self._conn.execute(
            "SELECT * FROM mitglied WHERE id = ?", (mitglied_id,)
        ).fetchone()
        if row is None:
            return None
        return Mitglied(id=row["id"], name=row["name"], gesperrt=bool(row["gesperrt"]))
