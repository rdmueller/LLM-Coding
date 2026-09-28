"""Issue 0007 (Ausgabe) und Issue 0008 (Verlängerung): BR-AUS-01..07, BR-NL-01."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.container import Anwendungskontext
from app.errors import ConflictError, ValidationError


def _kategorie(kontext: Anwendungskontext, *, leihdauer_tage=14, einweisungspflichtig=False):
    return kontext.katalog_service.kategorie_anlegen(
        "Zelt", leihdauer_tage, 20, einweisungspflichtig
    )


def _gegenstand(kontext: Anwendungskontext, kategorie_id: str, inventarnummer="INV-100"):
    return kontext.katalog_service.gegenstand_anlegen(inventarnummer, kategorie_id, 100)


def _mitglied(kontext: Anwendungskontext, name="Karim"):
    return kontext.mitglied_service.mitglied_anlegen(name)


def test_ausgabe_hinterlegt_kaution_und_setzt_rueckgabefrist_br_aus_05(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext, leihdauer_tage=14)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    erwartete_frist = date.today() + timedelta(days=14)
    assert ausleihe.rueckgabefrist == erwartete_frist.isoformat()
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    assert kaution is not None
    assert kaution.betrag == gegenstand.kaution


def test_ausgabe_nicht_verfuegbarer_gegenstand_wird_abgelehnt_br_aus_01(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    erstes_mitglied = _mitglied(kontext, "Karim")
    zweites_mitglied = _mitglied(kontext, "Fatima")
    kontext.ausleihe_service.ausgeben(gegenstand.id, erstes_mitglied.id)

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.ausgeben(gegenstand.id, zweites_mitglied.id)


def test_vierte_gleichzeitige_ausleihe_wird_abgelehnt_br_aus_02(kontext: Anwendungskontext) -> None:
    kategorie = _kategorie(kontext)
    mitglied = _mitglied(kontext)
    for i in range(3):
        gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer=f"INV-{i}")
        kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    vierter_gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-vierter")
    with pytest.raises(ValidationError):
        kontext.ausleihe_service.ausgeben(vierter_gegenstand.id, mitglied.id)


def test_gesperrtes_mitglied_leiht_nicht_aus_br_aus_03(kontext: Anwendungskontext) -> None:
    kategorie = _kategorie(kontext)
    erster_gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-A")
    zweiter_gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-B")
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(erster_gegenstand.id, mitglied.id)
    kontext.ausleihe_repository.rueckgabefrist_setzen(
        ausleihe.id, (date.today() - timedelta(days=1)).isoformat()
    )

    with pytest.raises(ValidationError):
        kontext.ausleihe_service.ausgeben(zweiter_gegenstand.id, mitglied.id)


def test_einweisungspflichtiger_gegenstand_ohne_einweisung_wird_abgelehnt_br_aus_04(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext, einweisungspflichtig=True)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    with pytest.raises(ValidationError):
        kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)


def test_eingewiesenes_mitglied_erhaelt_einweisungspflichtigen_gegenstand(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext, einweisungspflichtig=True)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    kontext.mitglied_service.einweisung_erfassen(mitglied.id, kategorie.id)

    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    assert ausleihe.gegenstand_id == gegenstand.id


def test_zwei_gleichzeitige_ausgabeversuche_genau_einer_gelingt_br_nl_01(
    kontext: Anwendungskontext,
) -> None:
    """BR-NL-01: Beide Versuche lesen denselben Ausgangszustand (Version), nur einer darf schreiben."""
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)

    gelesen_von_a = kontext.gegenstand_repository.finden(gegenstand.id)
    gelesen_von_b = kontext.gegenstand_repository.finden(gegenstand.id)

    erfolg_a = kontext.gegenstand_repository.zustand_wechseln_atomar(
        gelesen_von_a.id, "verfuegbar", "ausgeliehen", gelesen_von_a.version
    )
    erfolg_b = kontext.gegenstand_repository.zustand_wechseln_atomar(
        gelesen_von_b.id, "verfuegbar", "ausgeliehen", gelesen_von_b.version
    )

    assert erfolg_a is True
    assert erfolg_b is False


def test_einmalige_verlaengerung_verschiebt_rueckgabefrist_br_aus_06(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext, leihdauer_tage=14)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    alte_frist = date.fromisoformat(ausleihe.rueckgabefrist)

    verlaengert = kontext.ausleihe_service.verlaengern(ausleihe.id)

    assert verlaengert.verlaengert is True
    assert date.fromisoformat(verlaengert.rueckgabefrist) == alte_frist + timedelta(days=14)


def test_zweite_verlaengerung_wird_abgelehnt_br_aus_06(kontext: Anwendungskontext) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.ausleihe_service.verlaengern(ausleihe.id)

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.verlaengern(ausleihe.id)


def test_abgeschlossene_ausleihe_kann_nicht_verlaengert_werden_br_aus_08(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.verlaengern(ausleihe.id)


def test_mitglied_kann_nur_eigene_ausleihe_verlaengern_br_aus_08(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext, "Karim")
    anderes_mitglied = _mitglied(kontext, "Fatima")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    with pytest.raises(ValidationError):
        kontext.ausleihe_service.verlaengern(ausleihe.id, anfragendes_mitglied_id=anderes_mitglied.id)


def test_verlaengerung_bei_offener_vormerkung_wird_abgelehnt_br_aus_07(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    vormerkendes_mitglied = _mitglied(kontext, "Fatima")
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.vormerkung_repository.anlegen(
        kategorie.id, vormerkendes_mitglied.id, date.today().isoformat()
    )

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.verlaengern(ausleihe.id)


def test_verlaengerung_ueberfaelliger_ausleihe_wird_abgelehnt_br_aus_07(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext, leihdauer_tage=1)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    ueberfaellige_frist = date.today() - timedelta(days=1)
    kontext.ausleihe_repository.rueckgabefrist_setzen(ausleihe.id, ueberfaellige_frist.isoformat())

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.verlaengern(ausleihe.id)


def test_reservierendes_mitglied_kann_reservierten_gegenstand_abholen_br_vm_03(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-reserviert")
    ausleiher = _mitglied(kontext, "Karim")
    reservierendes_mitglied = _mitglied(kontext, "Fatima")
    ausleihe_erster = kontext.ausleihe_service.ausgeben(gegenstand.id, ausleiher.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.vormerkung_service.vormerken(kategorie.id, reservierendes_mitglied.id)
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")
    zwischenstand = kontext.gegenstand_repository.finden(gegenstand.id)
    assert zwischenstand.zustand == "reserviert"

    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, reservierendes_mitglied.id)

    assert ausleihe.mitglied_id == reservierendes_mitglied.id
    ergebnis = kontext.gegenstand_repository.finden(gegenstand.id)
    assert ergebnis.zustand == "ausgeliehen"
    reservierung = kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand.id)
    assert reservierung is None
    assert ausleihe_erster.id is not None


def test_anderes_mitglied_kann_reservierten_gegenstand_nicht_abholen_br_vm_03(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-reserviert-2")
    ausleiher = _mitglied(kontext, "Karim")
    reservierendes_mitglied = _mitglied(kontext, "Fatima")
    fremdes_mitglied = _mitglied(kontext, "Nora")
    kontext.ausleihe_service.ausgeben(gegenstand.id, ausleiher.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.vormerkung_service.vormerken(kategorie.id, reservierendes_mitglied.id)
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    with pytest.raises(ConflictError):
        kontext.ausleihe_service.ausgeben(gegenstand.id, fremdes_mitglied.id)


def test_ausgabe_rollt_bei_fehler_nach_zustandswechsel_vollstaendig_zurueck(
    kontext: Anwendungskontext, monkeypatch: pytest.MonkeyPatch
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    def kaputt(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(kontext.kaution_repository, "hinterlegen", kaputt)

    with pytest.raises(RuntimeError):
        kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    assert kontext.gegenstand_repository.finden(gegenstand.id).zustand == "verfuegbar"
    assert kontext.ausleihe_repository.finden_aktive_fuer_gegenstand(gegenstand.id) is None
