"""Repository für Vormerkung — minimale Grundlage für BR-AUS-07.

Vollständige Vormerkungs-Verwaltung (Anlegen über REST/CLI, Warteschlange) folgt in Epic 0016.
"""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Vormerkung
from app.repositories._transaction import commit_when_unmanaged


class VormerkungRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(self, kategorie_id: str, mitglied_id: str, eingangszeit: str) -> Vormerkung:
        vormerkung_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO vormerkung (id, kategorie_id, mitglied_id, eingangszeit) VALUES (?, ?, ?, ?)",
            (vormerkung_id, kategorie_id, mitglied_id, eingangszeit),
        )
        commit_when_unmanaged(self._conn)
        return Vormerkung(
            id=vormerkung_id, kategorie_id=kategorie_id, mitglied_id=mitglied_id, eingangszeit=eingangszeit
        )

    def hat_offene_vormerkung(self, kategorie_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM vormerkung WHERE kategorie_id = ?", (kategorie_id,)
        ).fetchone()
        return row is not None

    def entfernen_atomar(self, vormerkung_id: str) -> bool:  # BR-NL-02
        cursor = self._conn.execute("DELETE FROM vormerkung WHERE id = ?", (vormerkung_id,))
        commit_when_unmanaged(self._conn)
        return cursor.rowcount == 1

    def warteschlangenlaenge(self, kategorie_id: str) -> int:  # SUC-05
        row = self._conn.execute(
            "SELECT COUNT(*) AS anzahl FROM vormerkung WHERE kategorie_id = ?", (kategorie_id,)
        ).fetchone()
        return row["anzahl"]

    def warteschlange(self, kategorie_id: str) -> list[Vormerkung]:  # BR-VM-02
        rows = self._conn.execute(
            "SELECT * FROM vormerkung WHERE kategorie_id = ? ORDER BY eingangszeit", (kategorie_id,)
        ).fetchall()
        return [
            Vormerkung(
                id=row["id"],
                kategorie_id=row["kategorie_id"],
                mitglied_id=row["mitglied_id"],
                eingangszeit=row["eingangszeit"],
            )
            for row in rows
        ]
