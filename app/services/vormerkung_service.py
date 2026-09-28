"""VormerkungService — Kategorie vormerken (Issue 0017) und automatische Zuteilung (Issue 0018)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.errors import ConflictError, NotFoundError
from app.models import Reservierung, Vormerkung
from app.repositories.gegenstand_repository import GegenstandRepository
from app.repositories.kategorie_repository import KategorieRepository
from app.repositories.mitglied_repository import MitgliedRepository
from app.repositories._transaction import transaction
from app.repositories.reservierung_repository import ReservierungRepository
from app.repositories.vormerkung_repository import VormerkungRepository
from app.services.mitglied_service import MitgliedService
from app.services.oeffnungstage import verfallszeit_berechnen


class VormerkungService:
    def __init__(
        self,
        kategorie_repository: KategorieRepository,
        mitglied_repository: MitgliedRepository,
        vormerkung_repository: VormerkungRepository,
        gegenstand_repository: GegenstandRepository,
        mitglied_service: MitgliedService,
        reservierung_repository: ReservierungRepository,
    ) -> None:
        self._kategorie_repository = kategorie_repository
        self._mitglied_repository = mitglied_repository
        self._vormerkung_repository = vormerkung_repository
        self._gegenstand_repository = gegenstand_repository
        self._mitglied_service = mitglied_service
        self._reservierung_repository = reservierung_repository

    def vormerken(self, kategorie_id: str, mitglied_id: str) -> tuple[Vormerkung, int]:
        if self._kategorie_repository.finden(kategorie_id) is None:  # BR-VM-01
            raise NotFoundError(f"Kategorie {kategorie_id} nicht gefunden")
        if self._mitglied_repository.finden(mitglied_id) is None:  # BR-VM-01
            raise NotFoundError(f"Mitglied {mitglied_id} nicht gefunden")

        # BR-VM-08: keine Sperrprüfung — gesperrtes Mitglied darf vormerken
        eingangszeit = datetime.now(timezone.utc).isoformat()
        vormerkung = self._vormerkung_repository.anlegen(kategorie_id, mitglied_id, eingangszeit)

        warteschlange = self._vormerkung_repository.warteschlange(kategorie_id)  # BR-VM-02
        position = next(
            index + 1 for index, eintrag in enumerate(warteschlange) if eintrag.id == vormerkung.id
        )
        return vormerkung, position

    def zuteilen(self, gegenstand_id: str, kategorie_id: str) -> Reservierung | None:
        with transaction(self._gegenstand_repository._conn, immediate=True):
            warteschlange = self._vormerkung_repository.warteschlange(kategorie_id)
            for eintrag in warteschlange:
                if self._mitglied_service.ist_gesperrt(eintrag.mitglied_id):  # BR-VM-08
                    continue

                if not self._vormerkung_repository.entfernen_atomar(eintrag.id):  # BR-NL-02
                    return None

                gegenstand = self._gegenstand_repository.finden(gegenstand_id)
                erstellt_am = date.today()
                verfallszeit = verfallszeit_berechnen(erstellt_am)  # BR-VM-04
                reservierung = self._reservierung_repository.anlegen(
                    gegenstand_id, eintrag.mitglied_id, erstellt_am.isoformat(), verfallszeit.isoformat()
                )
                erfolgreich = self._gegenstand_repository.zustand_wechseln_atomar(
                    gegenstand_id, "verfuegbar", "reserviert", gegenstand.version
                )
                if not erfolgreich:
                    raise ConflictError("Gegenstand wurde inzwischen anderweitig verändert")
                return reservierung

            return None

    def verfall_pruefen(self, gegenstand_id: str) -> None:  # BR-VM-05
        with transaction(self._gegenstand_repository._conn, immediate=True):
            reservierung = self._reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand_id)
            if reservierung is None:
                return
            if date.fromisoformat(reservierung.verfallszeit) <= date.today():
                self._reservierung_repository.status_setzen(reservierung.id, "verfallen")
                gegenstand = self._gegenstand_repository.finden(gegenstand_id)
                erfolgreich = self._gegenstand_repository.zustand_wechseln_atomar(
                    gegenstand_id, "reserviert", "verfuegbar", gegenstand.version
                )
                if not erfolgreich:
                    raise ConflictError("Gegenstand wurde inzwischen anderweitig verändert")
                self.zuteilen(gegenstand_id, gegenstand.kategorie_id)
