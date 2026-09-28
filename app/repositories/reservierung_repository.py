"""ReservierungRepository — Reservierungen aus automatischer Zuteilung (Issue 0018)."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Reservierung
from app.repositories._transaction import commit_when_unmanaged


class ReservierungRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(
        self, gegenstand_id: str, mitglied_id: str, erstellt_am: str, verfallszeit: str
    ) -> Reservierung:
        reservierung_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO reservierung (id, gegenstand_id, mitglied_id, status, erstellt_am, verfallszeit) "
            "VALUES (?, ?, ?, 'aktiv', ?, ?)",
            (reservierung_id, gegenstand_id, mitglied_id, erstellt_am, verfallszeit),
        )
        commit_when_unmanaged(self._conn)
        return Reservierung(
            id=reservierung_id,
            gegenstand_id=gegenstand_id,
            mitglied_id=mitglied_id,
            status="aktiv",
            erstellt_am=erstellt_am,
            verfallszeit=verfallszeit,
        )

    def finden_aktiv_fuer_gegenstand(self, gegenstand_id: str) -> Reservierung | None:
        row = self._conn.execute(
            "SELECT * FROM reservierung WHERE gegenstand_id = ? AND status = 'aktiv'", (gegenstand_id,)
        ).fetchone()
        if row is None:
            return None
        return Reservierung(
            id=row["id"],
            gegenstand_id=row["gegenstand_id"],
            mitglied_id=row["mitglied_id"],
            status=row["status"],
            erstellt_am=row["erstellt_am"],
            verfallszeit=row["verfallszeit"],
        )

    def status_setzen(self, reservierung_id: str, neuer_status: str) -> None:
        self._conn.execute(
            "UPDATE reservierung SET status = ? WHERE id = ?", (neuer_status, reservierung_id)
        )
        commit_when_unmanaged(self._conn)
