"""RueckgabeService — Rücknahme an der Theke (Issue 0010) und Prüfprotokoll (Issue 0011).

BR-RP-01..05 (ADR-0003: ein Service je fachlichem Vorgang).
Erweitert um Nutzungszähler und Wartungsfälligkeit (Issue 0012, BR-WA-01, BR-WA-02).
"""
from __future__ import annotations

from datetime import date

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Gegenstand, Pruefprotokoll
from app.repositories.ausleihe_repository import AusleiheRepository
from app.repositories.gegenstand_repository import GegenstandRepository
from app.repositories.kategorie_repository import KategorieRepository
from app.repositories.kaution_repository import KautionRepository
from app.repositories.pruefprotokoll_repository import PruefprotokollRepository
from app.repositories._transaction import transaction
from app.services.audit_service import AuditService
from app.services.vormerkung_service import VormerkungService

ERGEBNISSE = {"unauffaellig", "wartungsfaellig", "verloren"}


class RueckgabeService:
    def __init__(
        self,
        gegenstand_repository: GegenstandRepository,
        ausleihe_repository: AusleiheRepository,
        kaution_repository: KautionRepository,
        pruefprotokoll_repository: PruefprotokollRepository,
        audit_service: AuditService,
        kategorie_repository: KategorieRepository,
        vormerkung_service: VormerkungService,
    ) -> None:
        self._gegenstand_repository = gegenstand_repository
        self._ausleihe_repository = ausleihe_repository
        self._kaution_repository = kaution_repository
        self._pruefprotokoll_repository = pruefprotokoll_repository
        self._audit_service = audit_service
        self._kategorie_repository = kategorie_repository
        self._vormerkung_service = vormerkung_service

    def zuruecknehmen(self, gegenstand_id: str, auffaelligkeit: str | None = None) -> Gegenstand:
        gegenstand = self._gegenstand_repository.finden(gegenstand_id)
        if gegenstand is None or gegenstand.zustand != "ausgeliehen":  # SUC-03
            raise NotFoundError(f"Gegenstand {gegenstand_id} ist nicht ausgeliehen")

        # BR-RP-01: Ausleihe bleibt offen, BR-RP-02: Kaution bleibt unverändert
        erfolgreich = self._gegenstand_repository.zustand_wechseln_atomar(
            gegenstand.id, "ausgeliehen", "in_pruefung", gegenstand.version
        )
        if not erfolgreich:
            raise ConflictError("Gegenstand wurde inzwischen anderweitig verändert")

        return self._gegenstand_repository.finden(gegenstand.id)

    def pruefung_abschliessen(
        self, gegenstand_id: str, ergebnis: str, abzug: int = 0, rolle: str = "wart"
    ) -> Pruefprotokoll:
        if ergebnis not in ERGEBNISSE:
            raise ValidationError(f"Unbekanntes Ergebnis: {ergebnis}")
        if rolle != "wart":  # BR-RP-03
            raise ValidationError("Nur der Wart erstellt das Prüfprotokoll", code="FORBIDDEN")

        gegenstand = self._gegenstand_repository.finden(gegenstand_id)
        if gegenstand is None:
            raise NotFoundError(f"Gegenstand {gegenstand_id} nicht gefunden")
        if gegenstand.zustand != "in_pruefung":  # BR-RP-03
            raise ConflictError("Gegenstand ist nicht in Prüfung")

        ausleihe = self._ausleihe_repository.finden_aktive_fuer_gegenstand(gegenstand_id)
        if ausleihe is None:
            raise ConflictError("Keine aktive Ausleihe für den Gegenstand gefunden")

        kaution = self._kaution_repository.finden_fuer_ausleihe(ausleihe.id)
        if kaution is None:
            raise ConflictError("Keine Kaution für die Ausleihe hinterlegt")

        if abzug > kaution.betrag:  # BR-KAU-02
            raise ValidationError("Abzug übersteigt die hinterlegte Kaution")

        # BR-RP-05: ein bereits vermerkter Schaden wird nicht erneut zugerechnet
        bereits_vermerkt = self._pruefprotokoll_repository.hat_vermerkten_schaden(gegenstand_id)
        if bereits_vermerkt:
            effektiver_abzug = 0
            schaden_vermerkt = False
        else:
            effektiver_abzug = abzug
            schaden_vermerkt = abzug > 0

        with transaction(self._gegenstand_repository._conn, immediate=True):
            if ergebnis == "verloren":  # BR-KAU-03
                self._kaution_repository.abzug_anwenden(kaution.id, kaution.betrag, voller_einbehalt=True)
                folgezustand = "ausgemustert"
                kaution_bewegung = kaution.betrag
            elif ergebnis == "unauffaellig":
                self._kaution_repository.abzug_anwenden(kaution.id, effektiver_abzug)
                neuer_zaehler = self._gegenstand_repository.nutzungszaehler_erhoehen(gegenstand.id)
                kategorie = self._kategorie_repository.finden(gegenstand.kategorie_id)
                folgezustand = (
                    "wartungsfaellig" if neuer_zaehler >= kategorie.wartungsintervall else "verfuegbar"
                )
                kaution_bewegung = kaution.betrag if effektiver_abzug == 0 else effektiver_abzug
            else:
                self._kaution_repository.abzug_anwenden(kaution.id, effektiver_abzug)
                folgezustand = "wartungsfaellig"
                kaution_bewegung = effektiver_abzug

            self._ausleihe_repository.abschliessen(ausleihe.id)  # BR-RP-04

            erfolgreich = self._gegenstand_repository.zustand_wechseln_atomar(
                gegenstand.id, "in_pruefung", folgezustand, gegenstand.version
            )
            if not erfolgreich:
                raise ConflictError("Gegenstand wurde inzwischen anderweitig verändert")

            if folgezustand == "verfuegbar":  # BR-VM-03
                self._vormerkung_service.zuteilen(gegenstand.id, gegenstand.kategorie_id)

            pruefprotokoll = self._pruefprotokoll_repository.anlegen(
                gegenstand_id=gegenstand.id,
                ausleihe_id=ausleihe.id,
                ergebnis=ergebnis,
                abzug=effektiver_abzug,
                schaden_vermerkt=schaden_vermerkt,
                erstellt_am=date.today().isoformat(),
            )

            self._audit_service.protokollieren(
                "kaution_bewegung",
                str(kaution_bewegung),
                f"pruefprotokoll:{pruefprotokoll.id}",
                kaution.id,
            )
            return pruefprotokoll
