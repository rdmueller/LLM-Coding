"""MitgliedService — Mitglieder und Einweisungen (Issue 0004, BR-AUS-04)."""
from __future__ import annotations

from datetime import date

from app.errors import NotFoundError
from app.models import Einweisung, Mitglied
from app.repositories.ausleihe_repository import AusleiheRepository
from app.repositories.einweisung_repository import EinweisungRepository
from app.repositories.kategorie_repository import KategorieRepository
from app.repositories.mitglied_repository import MitgliedRepository


class MitgliedService:
    def __init__(
        self,
        mitglied_repository: MitgliedRepository,
        einweisung_repository: EinweisungRepository,
        kategorie_repository: KategorieRepository,
        ausleihe_repository: AusleiheRepository,
    ) -> None:
        self._mitglied_repository = mitglied_repository
        self._einweisung_repository = einweisung_repository
        self._kategorie_repository = kategorie_repository
        self._ausleihe_repository = ausleihe_repository

    def mitglied_anlegen(self, name: str) -> Mitglied:
        return self._mitglied_repository.anlegen(name)

    def mitglied_lesen(self, mitglied_id: str) -> Mitglied:
        mitglied = self._mitglied_repository.finden(mitglied_id)
        if mitglied is None:
            raise NotFoundError(f"Mitglied {mitglied_id} nicht gefunden")
        return mitglied

    def einweisung_erfassen(self, mitglied_id: str, kategorie_id: str) -> Einweisung:
        if self._mitglied_repository.finden(mitglied_id) is None:
            raise NotFoundError(f"Mitglied {mitglied_id} nicht gefunden")
        if self._kategorie_repository.finden(kategorie_id) is None:
            raise NotFoundError(f"Kategorie {kategorie_id} nicht gefunden")
        return self._einweisung_repository.anlegen(
            mitglied_id, kategorie_id, date.today().isoformat()
        )

    def ist_eingewiesen(self, mitglied_id: str, kategorie_id: str) -> bool:
        return self._einweisung_repository.existiert(mitglied_id, kategorie_id)

    def ist_gesperrt(self, mitglied_id: str) -> bool:  # BR-SP-01
        return self._ausleihe_repository.hat_ueberfaellige_offene_ausleihen(
            mitglied_id, date.today().isoformat()
        )
