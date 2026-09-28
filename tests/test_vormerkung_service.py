"""Issue 0017: Kategorie vormerken (BR-VM-01, BR-VM-02, BR-VM-08).
Issue 0018: Automatische Reservierungszuteilung (BR-VM-03..06, BR-VM-08, BR-NL-02).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.container import Anwendungskontext
from app.errors import ConflictError, NotFoundError
from app.services.oeffnungstage import verfallszeit_berechnen


def _kategorie(kontext: Anwendungskontext, *, leihdauer_tage=14, einweisungspflichtig=False):
    return kontext.katalog_service.kategorie_anlegen(
        "Zelt", leihdauer_tage, 20, einweisungspflichtig
    )


def _gegenstand(kontext: Anwendungskontext, kategorie_id: str, inventarnummer="INV-100"):
    return kontext.katalog_service.gegenstand_anlegen(inventarnummer, kategorie_id, 100)


def _mitglied(kontext: Anwendungskontext, name="Karim"):
    return kontext.mitglied_service.mitglied_anlegen(name)


def test_zweite_vormerkung_landet_an_position_zwei_br_vm_01_02(kontext: Anwendungskontext) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)
    mitglied_a = kontext.mitglied_service.mitglied_anlegen("Karim")
    mitglied_b = kontext.mitglied_service.mitglied_anlegen("Lena")

    _, position_a = kontext.vormerkung_service.vormerken(kategorie.id, mitglied_a.id)
    vormerkung_b, position_b = kontext.vormerkung_service.vormerken(kategorie.id, mitglied_b.id)

    assert position_a == 1
    assert position_b == 2
    assert vormerkung_b.kategorie_id == kategorie.id
    assert vormerkung_b.mitglied_id == mitglied_b.id


def test_gesperrtes_mitglied_darf_vormerken_br_vm_08(kontext: Anwendungskontext) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)
    gegenstand = kontext.katalog_service.gegenstand_anlegen("INV-100", kategorie.id, 100)
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.ausleihe_repository.rueckgabefrist_setzen(
        ausleihe.id, (date.today() - timedelta(days=1)).isoformat()
    )
    assert kontext.mitglied_service.ist_gesperrt(mitglied.id)

    vormerkung, position = kontext.vormerkung_service.vormerken(kategorie.id, mitglied.id)

    assert position == 1
    assert vormerkung.mitglied_id == mitglied.id


def test_vormerken_mit_unbekannter_kategorie_wirft_not_found(kontext: Anwendungskontext) -> None:
    mitglied = kontext.mitglied_service.mitglied_anlegen("Karim")

    with pytest.raises(NotFoundError):
        kontext.vormerkung_service.vormerken("unbekannt", mitglied.id)


def test_vormerken_mit_unbekanntem_mitglied_wirft_not_found(kontext: Anwendungskontext) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 20, False)

    with pytest.raises(NotFoundError):
        kontext.vormerkung_service.vormerken(kategorie.id, "unbekannt")


def test_pruefung_abschliessen_verfuegbar_reserviert_fuer_vormerkendes_mitglied_br_vm_03(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    ausleiher = _mitglied(kontext, "Karim")
    vormerker = _mitglied(kontext, "Fatima")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, ausleiher.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.vormerkung_service.vormerken(kategorie.id, vormerker.id)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    ergebnis = kontext.gegenstand_repository.finden(gegenstand.id)
    assert ergebnis.zustand == "reserviert"
    reservierung = kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand.id)
    assert reservierung is not None
    assert reservierung.mitglied_id == vormerker.id
    assert ausleihe.id is not None


def test_verfallszeit_ab_mittwoch_ergibt_folgenden_samstag_br_vm_04(kontext: Anwendungskontext) -> None:
    mittwoch = date(2024, 1, 3)  # weekday() == 2

    verfallszeit = verfallszeit_berechnen(mittwoch)

    assert verfallszeit == date(2024, 1, 9)  # Samstag + 3 Kalendertage -> Dienstag


def test_verfallszeit_ab_samstag_ergibt_denselben_dienstag_br_vm_04(kontext: Anwendungskontext) -> None:
    samstag = date(2024, 1, 6)  # weekday() == 5, ist bereits Öffnungstag

    verfallszeit = verfallszeit_berechnen(samstag)

    assert verfallszeit == date(2024, 1, 9)  # Samstag + 3 Kalendertage -> Dienstag


def test_pruefung_abschliessen_wartungsfaellig_laesst_warteschlange_unangetastet_br_vm_06(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    ausleiher = _mitglied(kontext, "Karim")
    vormerker = _mitglied(kontext, "Fatima")
    kontext.ausleihe_service.ausgeben(gegenstand.id, ausleiher.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.vormerkung_service.vormerken(kategorie.id, vormerker.id)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "wartungsfaellig")

    ergebnis = kontext.gegenstand_repository.finden(gegenstand.id)
    assert ergebnis.zustand == "wartungsfaellig"
    assert kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand.id) is None
    warteschlange = kontext.vormerkung_repository.warteschlange(kategorie.id)
    assert len(warteschlange) == 1
    assert warteschlange[0].mitglied_id == vormerker.id


def test_gesperrtes_erstes_mitglied_wird_uebersprungen_zweites_erhaelt_reservierung_br_vm_08(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-frei")
    gesperrtes_mitglied = _mitglied(kontext, "Karim")
    zweites_mitglied = _mitglied(kontext, "Fatima")
    ausleihe = kontext.ausleihe_service.ausgeben(
        _gegenstand(kontext, kategorie.id, inventarnummer="INV-anderer").id, gesperrtes_mitglied.id
    )
    kontext.ausleihe_repository.rueckgabefrist_setzen(
        ausleihe.id, (date.today() - timedelta(days=1)).isoformat()
    )
    assert kontext.mitglied_service.ist_gesperrt(gesperrtes_mitglied.id)
    kontext.vormerkung_service.vormerken(kategorie.id, gesperrtes_mitglied.id)
    kontext.vormerkung_service.vormerken(kategorie.id, zweites_mitglied.id)

    reservierung = kontext.vormerkung_service.zuteilen(gegenstand.id, kategorie.id)

    assert reservierung is not None
    assert reservierung.mitglied_id == zweites_mitglied.id
    warteschlange = kontext.vormerkung_repository.warteschlange(kategorie.id)
    assert len(warteschlange) == 1
    assert warteschlange[0].mitglied_id == gesperrtes_mitglied.id


def test_zwei_gleichzeitige_entfernen_versuche_nur_einer_gelingt_br_nl_02(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    mitglied = _mitglied(kontext)
    vormerkung, _ = kontext.vormerkung_service.vormerken(kategorie.id, mitglied.id)

    warteschlange_a = kontext.vormerkung_repository.warteschlange(kategorie.id)
    warteschlange_b = kontext.vormerkung_repository.warteschlange(kategorie.id)

    erfolg_a = kontext.vormerkung_repository.entfernen_atomar(warteschlange_a[0].id)
    erfolg_b = kontext.vormerkung_repository.entfernen_atomar(warteschlange_b[0].id)

    assert erfolg_a is True
    assert erfolg_b is False


def test_zuteilen_rollt_entfernte_warteschlange_bei_konflikt_zurueck(
    kontext: Anwendungskontext, monkeypatch: pytest.MonkeyPatch
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    kontext.vormerkung_service.vormerken(kategorie.id, mitglied.id)

    monkeypatch.setattr(kontext.gegenstand_repository, "zustand_wechseln_atomar", lambda *args: False)

    with pytest.raises(ConflictError):
        kontext.vormerkung_service.zuteilen(gegenstand.id, kategorie.id)

    assert len(kontext.vormerkung_repository.warteschlange(kategorie.id)) == 1
    assert kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand.id) is None
