"""Container: verdrahtet Repositories und Services aus einer SQLite-Verbindung (ADR-0003).

REST-Controller und CLI-Befehle rufen dieselbe Service-Schicht auf.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.repositories.audit_repository import AuditRepository
from app.repositories.ausleihe_repository import AusleiheRepository
from app.repositories.einweisung_repository import EinweisungRepository
from app.repositories.gegenstand_repository import GegenstandRepository
from app.repositories.kategorie_repository import KategorieRepository
from app.repositories.kaution_repository import KautionRepository
from app.repositories.mitglied_repository import MitgliedRepository
from app.repositories.pruefprotokoll_repository import PruefprotokollRepository
from app.repositories.reservierung_repository import ReservierungRepository
from app.repositories.vormerkung_repository import VormerkungRepository
from app.services.audit_service import AuditService
from app.services.ausleihe_service import AusleiheService
from app.services.katalog_service import KatalogService
from app.services.mitglied_service import MitgliedService
from app.services.rueckgabe_service import RueckgabeService
from app.services.vormerkung_service import VormerkungService
from app.services.wartung_service import WartungService


@dataclass
class Anwendungskontext:
    kategorie_repository: KategorieRepository
    gegenstand_repository: GegenstandRepository
    mitglied_repository: MitgliedRepository
    einweisung_repository: EinweisungRepository
    ausleihe_repository: AusleiheRepository
    kaution_repository: KautionRepository
    vormerkung_repository: VormerkungRepository
    pruefprotokoll_repository: PruefprotokollRepository
    reservierung_repository: ReservierungRepository
    audit_repository: AuditRepository
    katalog_service: KatalogService
    mitglied_service: MitgliedService
    audit_service: AuditService
    ausleihe_service: AusleiheService
    rueckgabe_service: RueckgabeService
    vormerkung_service: VormerkungService
    wartung_service: WartungService


def erstellen(conn: sqlite3.Connection) -> Anwendungskontext:
    kategorie_repository = KategorieRepository(conn)
    gegenstand_repository = GegenstandRepository(conn)
    mitglied_repository = MitgliedRepository(conn)
    einweisung_repository = EinweisungRepository(conn)
    ausleihe_repository = AusleiheRepository(conn)
    kaution_repository = KautionRepository(conn)
    vormerkung_repository = VormerkungRepository(conn)
    pruefprotokoll_repository = PruefprotokollRepository(conn)
    reservierung_repository = ReservierungRepository(conn)
    audit_repository = AuditRepository(conn)

    katalog_service = KatalogService(kategorie_repository, gegenstand_repository, vormerkung_repository)
    mitglied_service = MitgliedService(
        mitglied_repository, einweisung_repository, kategorie_repository, ausleihe_repository
    )
    audit_service = AuditService(audit_repository)
    vormerkung_service = VormerkungService(
        kategorie_repository=kategorie_repository,
        mitglied_repository=mitglied_repository,
        vormerkung_repository=vormerkung_repository,
        gegenstand_repository=gegenstand_repository,
        mitglied_service=mitglied_service,
        reservierung_repository=reservierung_repository,
    )
    ausleihe_service = AusleiheService(
        gegenstand_repository=gegenstand_repository,
        kategorie_repository=kategorie_repository,
        mitglied_repository=mitglied_repository,
        ausleihe_repository=ausleihe_repository,
        kaution_repository=kaution_repository,
        vormerkung_repository=vormerkung_repository,
        mitglied_service=mitglied_service,
        audit_service=audit_service,
        vormerkung_service=vormerkung_service,
        reservierung_repository=reservierung_repository,
    )
    rueckgabe_service = RueckgabeService(
        gegenstand_repository=gegenstand_repository,
        ausleihe_repository=ausleihe_repository,
        kaution_repository=kaution_repository,
        pruefprotokoll_repository=pruefprotokoll_repository,
        audit_service=audit_service,
        kategorie_repository=kategorie_repository,
        vormerkung_service=vormerkung_service,
    )
    wartung_service = WartungService(
        gegenstand_repository=gegenstand_repository, vormerkung_service=vormerkung_service
    )

    return Anwendungskontext(
        kategorie_repository=kategorie_repository,
        gegenstand_repository=gegenstand_repository,
        mitglied_repository=mitglied_repository,
        einweisung_repository=einweisung_repository,
        ausleihe_repository=ausleihe_repository,
        kaution_repository=kaution_repository,
        vormerkung_repository=vormerkung_repository,
        pruefprotokoll_repository=pruefprotokoll_repository,
        reservierung_repository=reservierung_repository,
        audit_repository=audit_repository,
        katalog_service=katalog_service,
        mitglied_service=mitglied_service,
        audit_service=audit_service,
        ausleihe_service=ausleihe_service,
        rueckgabe_service=rueckgabe_service,
        vormerkung_service=vormerkung_service,
        wartung_service=wartung_service,
    )
