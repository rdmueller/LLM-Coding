"""Issue 0004: Mitglied-Stammdaten und Einweisung (BR-AUS-04).
Issue 0020: abgeleiteter Sperrstatus (BR-SP-01..03).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.container import Anwendungskontext
from app.errors import NotFoundError


def test_einweisung_gilt_nur_fuer_ihre_kategorie(kontext: Anwendungskontext) -> None:
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")
    kategorie_a = kontext.katalog_service.kategorie_anlegen("Kettensäge", 7, 10, True)
    kategorie_b = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)

    assert not kontext.mitglied_service.ist_eingewiesen(mitglied.id, kategorie_a.id)

    kontext.mitglied_service.einweisung_erfassen(mitglied.id, kategorie_a.id)

    assert kontext.mitglied_service.ist_eingewiesen(mitglied.id, kategorie_a.id)
    assert not kontext.mitglied_service.ist_eingewiesen(mitglied.id, kategorie_b.id)


def test_mitglied_mit_ueberfaelliger_ausleihe_ist_gesperrt_br_sp_01_02(
    kontext: Anwendungskontext,
) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)
    gegenstand = kontext.katalog_service.gegenstand_anlegen("INV-100", kategorie.id, 100)
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.ausleihe_repository.rueckgabefrist_setzen(
        ausleihe.id, (date.today() - timedelta(days=1)).isoformat()
    )

    assert kontext.mitglied_service.ist_gesperrt(mitglied.id)


def test_mitglied_ohne_ueberfaellige_ausleihe_ist_nicht_gesperrt_br_sp_01_02(
    kontext: Anwendungskontext,
) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)
    gegenstand = kontext.katalog_service.gegenstand_anlegen("INV-100", kategorie.id, 100)
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")
    kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    assert not kontext.mitglied_service.ist_gesperrt(mitglied.id)


def test_mitglied_bleibt_gesperrt_bis_pruefung_abgeschlossen_br_sp_03(
    kontext: Anwendungskontext,
) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)
    gegenstand = kontext.katalog_service.gegenstand_anlegen("INV-100", kategorie.id, 100)
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.ausleihe_repository.rueckgabefrist_setzen(
        ausleihe.id, (date.today() - timedelta(days=1)).isoformat()
    )

    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    assert kontext.mitglied_service.ist_gesperrt(mitglied.id)

    kontext.rueckgabe_service.pruefung_abschliessen(
        gegenstand.id, ergebnis="unauffaellig", rolle="wart"
    )
    assert not kontext.mitglied_service.ist_gesperrt(mitglied.id)


def test_einweisung_mit_unbekannter_kategorie_wird_mit_not_found_abgelehnt(
    kontext: Anwendungskontext,
) -> None:
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")

    with pytest.raises(NotFoundError):
        kontext.mitglied_service.einweisung_erfassen(mitglied.id, "unbekannt")
