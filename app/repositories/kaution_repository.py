"""Repository für Kaution (BR-AUS-05, BR-KAU-01)."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Kaution
from app.repositories._transaction import commit_when_unmanaged


class KautionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def hinterlegen(self, ausleihe_id: str, betrag: int) -> Kaution:
        kaution_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO kaution (id, ausleihe_id, betrag, status) VALUES (?, ?, ?, 'hinterlegt')",
            (kaution_id, ausleihe_id, betrag),
        )
        commit_when_unmanaged(self._conn)
        return Kaution(id=kaution_id, ausleihe_id=ausleihe_id, betrag=betrag, status="hinterlegt")

    def finden_fuer_ausleihe(self, ausleihe_id: str) -> Kaution | None:
        row = self._conn.execute(
            "SELECT * FROM kaution WHERE ausleihe_id = ?", (ausleihe_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_kaution(row)

    def finden(self, kaution_id: str) -> Kaution | None:
        row = self._conn.execute(
            "SELECT * FROM kaution WHERE id = ?", (kaution_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_kaution(row)

    def abzug_anwenden(self, kaution_id: str, abzug: int, voller_einbehalt: bool = False) -> Kaution:
        """BR-KAU-03/BR-KAU-04: passt den verbleibenden Kautionssaldo und den Status an."""
        kaution = self.finden(kaution_id)
        if voller_einbehalt or abzug == kaution.betrag:
            neuer_betrag = 0
            status = "einbehalten"
        elif abzug > 0:
            neuer_betrag = max(kaution.betrag - abzug, 0)
            status = "teilweise_einbehalten"
        else:
            neuer_betrag = 0
            status = "freigegeben"
        self._conn.execute(
            "UPDATE kaution SET betrag = ?, status = ? WHERE id = ?",
            (neuer_betrag, status, kaution_id),
        )
        commit_when_unmanaged(self._conn)
        return Kaution(id=kaution.id, ausleihe_id=kaution.ausleihe_id, betrag=neuer_betrag, status=status)


def _to_kaution(row: sqlite3.Row) -> Kaution:
    return Kaution(
        id=row["id"], ausleihe_id=row["ausleihe_id"], betrag=row["betrag"], status=row["status"]
    )
