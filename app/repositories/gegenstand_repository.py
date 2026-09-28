"""Repository für Gegenstand, inkl. optimistischem Locking (ADR-0006, BR-NL-01)."""
from __future__ import annotations

import sqlite3
import uuid

from app.models import Gegenstand
from app.repositories._transaction import commit_when_unmanaged


class GegenstandRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def anlegen(
        self,
        inventarnummer: str,
        kategorie_id: str,
        wiederbeschaffungswert: float,
        kaution: int,
    ) -> Gegenstand:
        gegenstand_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO gegenstand (id, inventarnummer, kategorie_id, "
            "wiederbeschaffungswert, kaution, nutzungszaehler, zustand, version) "
            "VALUES (?, ?, ?, ?, ?, 0, 'verfuegbar', 0)",
            (gegenstand_id, inventarnummer, kategorie_id, wiederbeschaffungswert, kaution),
        )
        commit_when_unmanaged(self._conn)
        return Gegenstand(
            id=gegenstand_id,
            inventarnummer=inventarnummer,
            kategorie_id=kategorie_id,
            wiederbeschaffungswert=wiederbeschaffungswert,
            kaution=kaution,
            nutzungszaehler=0,
            zustand="verfuegbar",
            version=0,
        )

    def inventarnummer_existiert(self, inventarnummer: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM gegenstand WHERE inventarnummer = ?", (inventarnummer,)
        ).fetchone()
        return row is not None

    def finden(self, gegenstand_id: str) -> Gegenstand | None:
        row = self._conn.execute(
            "SELECT * FROM gegenstand WHERE id = ?", (gegenstand_id,)
        ).fetchone()
        if row is None:
            return None
        return _to_gegenstand(row)

    def anzahl_verfuegbar_fuer_kategorie(self, kategorie_id: str) -> int:  # SUC-05
        row = self._conn.execute(
            "SELECT COUNT(*) AS anzahl FROM gegenstand WHERE kategorie_id = ? AND zustand = 'verfuegbar'",
            (kategorie_id,),
        ).fetchone()
        return row["anzahl"]

    def zustand_wechseln_atomar(
        self, gegenstand_id: str, erwarteter_zustand: str, neuer_zustand: str, version: int
    ) -> bool:
        """BR-NL-01: Schreibt nur, wenn Zustand und Version seit dem Lesen unverändert sind.

        Gibt True zurück, wenn genau eine Zeile getroffen wurde, sonst False (Konflikt).
        """
        cursor = self._conn.execute(
            "UPDATE gegenstand SET zustand = ?, version = version + 1 "
            "WHERE id = ? AND zustand = ? AND version = ?",
            (neuer_zustand, gegenstand_id, erwarteter_zustand, version),
        )
        commit_when_unmanaged(self._conn)
        return cursor.rowcount == 1

    def nutzungszaehler_erhoehen(self, gegenstand_id: str) -> int:
        """BR-WA-01: erhöht den Nutzungszähler um 1 und gibt den neuen Wert zurück."""
        self._conn.execute(
            "UPDATE gegenstand SET nutzungszaehler = nutzungszaehler + 1 WHERE id = ?",
            (gegenstand_id,),
        )
        commit_when_unmanaged(self._conn)
        row = self._conn.execute(
            "SELECT nutzungszaehler FROM gegenstand WHERE id = ?", (gegenstand_id,)
        ).fetchone()
        return row["nutzungszaehler"]

    def nutzungszaehler_zuruecksetzen(self, gegenstand_id: str) -> None:
        """BR-WA-03: setzt den Nutzungszähler nach abgeschlossener Wartung auf null."""
        self._conn.execute(
            "UPDATE gegenstand SET nutzungszaehler = 0 WHERE id = ?", (gegenstand_id,)
        )
        commit_when_unmanaged(self._conn)

    def zustand_setzen(
        self, gegenstand_id: str, neuer_zustand: str, erwarteter_version: int
    ) -> bool:
        """BR-VM-07: Zustandswechsel ohne Vorbedingung an den Ausgangszustand (z. B. Ausmusterung)."""
        cursor = self._conn.execute(
            "UPDATE gegenstand SET zustand = ?, version = version + 1 "
            "WHERE id = ? AND version = ?",
            (neuer_zustand, gegenstand_id, erwarteter_version),
        )
        commit_when_unmanaged(self._conn)
        return cursor.rowcount == 1

def _to_gegenstand(row: sqlite3.Row) -> Gegenstand:
    return Gegenstand(
        id=row["id"],
        inventarnummer=row["inventarnummer"],
        kategorie_id=row["kategorie_id"],
        wiederbeschaffungswert=row["wiederbeschaffungswert"],
        kaution=row["kaution"],
        nutzungszaehler=row["nutzungszaehler"],
        zustand=row["zustand"],
        version=row["version"],
    )
