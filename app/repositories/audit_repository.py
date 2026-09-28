"""Repository für den append-only Audit-Log (Issue 0005, BR-KAU-04)."""
from __future__ import annotations

import sqlite3
import uuid

from app.repositories._transaction import commit_when_unmanaged


class AuditRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def eintragen(
        self,
        zeitstempel: str,
        ereignis_typ: str,
        betrag_oder_zustand: str,
        ausloeser: str,
        referenz_id: str,
    ) -> str:
        eintrag_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO audit_log (id, zeitstempel, ereignis_typ, betrag_oder_zustand, "
            "ausloeser, referenz_id) VALUES (?, ?, ?, ?, ?, ?)",
            (eintrag_id, zeitstempel, ereignis_typ, betrag_oder_zustand, ausloeser, referenz_id),
        )
        commit_when_unmanaged(self._conn)
        return eintrag_id

    def alle_fuer(self, referenz_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM audit_log WHERE referenz_id = ? ORDER BY zeitstempel",
            (referenz_id,),
        ).fetchall()
