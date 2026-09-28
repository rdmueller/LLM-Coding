"""Repository für Ausleihe."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Ausleihe
from app.repositories._transaction import commit_when_unmanaged


class AusleiheRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(
        self,
        gegenstand_id: str,
        mitglied_id: str,
        ausgabedatum: str,
        rueckgabefrist: str,
    ) -> Ausleihe:
        ausleihe_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO ausleihe (id, gegenstand_id, mitglied_id, ausgabedatum, "
            "rueckgabefrist, verlaengert, status) VALUES (?, ?, ?, ?, ?, 0, 'aktiv')",
            (ausleihe_id, gegenstand_id, mitglied_id, ausgabedatum, rueckgabefrist),
        )
        commit_when_unmanaged(self._conn)
        return Ausleihe(
            id=ausleihe_id,
            gegenstand_id=gegenstand_id,
            mitglied_id=mitglied_id,
            ausgabedatum=ausgabedatum,
            rueckgabefrist=rueckgabefrist,
            verlaengert=False,
            status="aktiv",
        )

    def finden(self, ausleihe_id: str) -> Ausleihe | None:
        row = self._conn.execute(
            "SELECT * FROM ausleihe WHERE id = ?", (ausleihe_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_ausleihe(row)

    def anzahl_aktiver_ausleihen(self, mitglied_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS anzahl FROM ausleihe WHERE mitglied_id = ? AND status = 'aktiv'",
            (mitglied_id,),
        ).fetchone()
        return row["anzahl"]

    def verlaengern(self, ausleihe_id: str, neue_rueckgabefrist: str) -> None:
        self._conn.execute(
            "UPDATE ausleihe SET rueckgabefrist = ?, verlaengert = 1 WHERE id = ?",
            (neue_rueckgabefrist, ausleihe_id),
        )
        commit_when_unmanaged(self._conn)

    def rueckgabefrist_setzen(self, ausleihe_id: str, rueckgabefrist: str) -> None:
        """Test-Hilfsmethode, um Überfälligkeit zu simulieren (Sperr-Berechnung folgt in Epic 0019)."""
        self._conn.execute(
            "UPDATE ausleihe SET rueckgabefrist = ? WHERE id = ?", (rueckgabefrist, ausleihe_id)
        )
        commit_when_unmanaged(self._conn)

    def finden_aktive_fuer_gegenstand(self, gegenstand_id: str) -> Ausleihe | None:
        row = self._conn.execute(
            "SELECT * FROM ausleihe WHERE gegenstand_id = ? AND status = 'aktiv'", (gegenstand_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_ausleihe(row)

    def abschliessen(self, ausleihe_id: str) -> None:  # BR-RP-04
        self._conn.execute(
            "UPDATE ausleihe SET status = 'abgeschlossen' WHERE id = ?", (ausleihe_id,)
        )
        commit_when_unmanaged(self._conn)

    def hat_ueberfaellige_offene_ausleihen(self, mitglied_id: str, heute: str) -> bool:  # BR-SP-02
        row = self._conn.execute(
            "SELECT 1 FROM ausleihe WHERE mitglied_id = ? AND status != 'abgeschlossen' "
            "AND rueckgabefrist < ? LIMIT 1",
            (mitglied_id, heute),
        ).fetchone()
        return row is not None


def _to_ausleihe(row: sqlite3.Row) -> Ausleihe:
    return Ausleihe(
        id=row["id"],
        gegenstand_id=row["gegenstand_id"],
        mitglied_id=row["mitglied_id"],
        ausgabedatum=row["ausgabedatum"],
        rueckgabefrist=row["rueckgabefrist"],
        verlaengert=bool(row["verlaengert"]),
        status=row["status"],
    )
