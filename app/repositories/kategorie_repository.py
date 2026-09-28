"""Repository für Kategorie (ein Repository je Aggregat, ADR-0003)."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Kategorie
from app.repositories._transaction import commit_when_unmanaged


class KategorieRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(
        self,
        name: str,
        leihdauer_tage: int,
        wartungsintervall: int,
        einweisungspflichtig: bool,
    ) -> Kategorie:
        kategorie_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO kategorie (id, name, leihdauer_tage, wartungsintervall, "
            "einweisungspflichtig) VALUES (?, ?, ?, ?, ?)",
            (kategorie_id, name, leihdauer_tage, wartungsintervall, int(einweisungspflichtig)),
        )
        commit_when_unmanaged(self._conn)
        return Kategorie(kategorie_id, name, leihdauer_tage, wartungsintervall, einweisungspflichtig)

    def finden(self, kategorie_id: str) -> Kategorie | None:
        row = self._conn.execute(
            "SELECT * FROM kategorie WHERE id = ?", (kategorie_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_kategorie(row)


def _to_kategorie(row: sqlite3.Row) -> Kategorie:
    return Kategorie(
        id=row["id"],
        name=row["name"],
        leihdauer_tage=row["leihdauer_tage"],
        wartungsintervall=row["wartungsintervall"],
        einweisungspflichtig=bool(row["einweisungspflichtig"]),
    )
