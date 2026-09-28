"""Repository für Pruefprotokoll (Issue 0011, BR-RP-05)."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Pruefprotokoll
from app.repositories._transaction import commit_when_unmanaged


class PruefprotokollRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(
        self,
        gegenstand_id: str,
        ausleihe_id: str,
        ergebnis: str,
        abzug: int,
        schaden_vermerkt: bool,
        erstellt_am: str,
    ) -> Pruefprotokoll:
        protokoll_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO pruefprotokoll (id, gegenstand_id, ausleihe_id, ergebnis, abzug, "
            "schaden_vermerkt, erstellt_am) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                protokoll_id,
                gegenstand_id,
                ausleihe_id,
                ergebnis,
                abzug,
                int(schaden_vermerkt),
                erstellt_am,
            ),
        )
        commit_when_unmanaged(self._conn)
        return Pruefprotokoll(
            id=protokoll_id,
            gegenstand_id=gegenstand_id,
            ausleihe_id=ausleihe_id,
            ergebnis=ergebnis,
            abzug=abzug,
            schaden_vermerkt=schaden_vermerkt,
            erstellt_am=erstellt_am,
        )

    def hat_vermerkten_schaden(self, gegenstand_id: str) -> bool:  # BR-RP-05
        row = self._conn.execute(
            "SELECT 1 FROM pruefprotokoll WHERE gegenstand_id = ? AND schaden_vermerkt = 1",
            (gegenstand_id,),
        ).fetchone()
        return row is not None
