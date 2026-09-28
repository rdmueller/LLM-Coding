"""Issue 0010 (Gegenstand zurücknehmen): BR-RP-01, BR-RP-02.
Issue 0011 (Prüfprotokoll abschließen): BR-RP-03..05, BR-KAU-01..04.
Issue 0012 (Nutzungszähler und Wartungsfälligkeit): BR-WA-01, BR-WA-02.
"""
from __future__ import annotations

import pytest

from app.container import Anwendungskontext
from app.errors import ConflictError, NotFoundError, ValidationError


def _kategorie(kontext: Anwendungskontext, *, leihdauer_tage=14, einweisungspflichtig=False):
    return kontext.katalog_service.kategorie_anlegen(
        "Zelt", leihdauer_tage, 20, einweisungspflichtig
    )


def _gegenstand(kontext: Anwendungskontext, kategorie_id: str, inventarnummer="INV-100"):
    return kontext.katalog_service.gegenstand_anlegen(inventarnummer, kategorie_id, 100)


def _mitglied(kontext: Anwendungskontext, name="Karim"):
    return kontext.mitglied_service.mitglied_anlegen(name)


def test_rueckgabe_versetzt_gegenstand_in_pruefung_ausleihe_bleibt_aktiv_br_rp_01(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)

    zurueckgenommen = kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)

    assert zurueckgenommen.zustand == "in_pruefung"
    aktive_ausleihe = kontext.ausleihe_repository.finden(ausleihe.id)
    assert aktive_ausleihe.status == "aktiv"


def test_kaution_bleibt_nach_rueckgabe_mit_auffaelligkeit_unveraendert_br_rp_02(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kaution_vorher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id, auffaelligkeit="Riss im Stoff")

    kaution_nachher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    assert kaution_nachher.betrag == kaution_vorher.betrag
    assert kaution_nachher.status == kaution_vorher.status


def test_rueckgabe_nicht_ausgeliehener_gegenstand_wird_abgelehnt(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)

    with pytest.raises(NotFoundError):
        kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)


def test_rueckgabe_unbekannter_gegenstand_wird_abgelehnt(kontext: Anwendungskontext) -> None:
    with pytest.raises(NotFoundError):
        kontext.rueckgabe_service.zuruecknehmen("unbekannt")


def _in_pruefung_mit_ausleihe(kontext: Anwendungskontext, inventarnummer="INV-100"):
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer=inventarnummer)
    mitglied = _mitglied(kontext)
    ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    return gegenstand, ausleihe


def test_pruefung_durch_thekendienst_wird_abgelehnt_br_rp_03(kontext: Anwendungskontext) -> None:
    gegenstand, _ = _in_pruefung_mit_ausleihe(kontext)

    with pytest.raises(ValidationError):
        kontext.rueckgabe_service.pruefung_abschliessen(
            gegenstand.id, "unauffaellig", rolle="thekendienst"
        )


def test_abzug_ueber_kaution_wird_abgelehnt_br_kau_02(kontext: Anwendungskontext) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    with pytest.raises(ValidationError):
        kontext.rueckgabe_service.pruefung_abschliessen(
            gegenstand.id, "wartungsfaellig", abzug=kaution.betrag + 5
        )


def test_verloren_behaelt_volle_kaution_ein_und_mustert_aus_br_kau_03(
    kontext: Anwendungskontext,
) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "verloren")

    kaution_nachher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    gegenstand_nachher = kontext.gegenstand_repository.finden(gegenstand.id)
    assert kaution_nachher.status == "einbehalten"
    assert kaution_nachher.betrag == 0
    assert gegenstand_nachher.zustand == "ausgemustert"


def test_pruefung_abschliessen_schliesst_die_ausleihe_ab_br_rp_04(
    kontext: Anwendungskontext,
) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    ausleihe_nachher = kontext.ausleihe_repository.finden(ausleihe.id)
    assert ausleihe_nachher.status == "abgeschlossen"
    gegenstand_nachher = kontext.gegenstand_repository.finden(gegenstand.id)
    assert gegenstand_nachher.zustand == "verfuegbar"


def test_pruefung_abschliessen_wartungsfaellig_setzt_zustand_br_rp_06(
    kontext: Anwendungskontext,
) -> None:
    gegenstand, _ = _in_pruefung_mit_ausleihe(kontext)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "wartungsfaellig")

    gegenstand_nachher = kontext.gegenstand_repository.finden(gegenstand.id)
    assert gegenstand_nachher.zustand == "wartungsfaellig"


def test_bereits_vermerkter_schaden_wird_nicht_erneut_zugerechnet_br_rp_05(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    # Erste Ausleihe: Schaden wird im Prüfprotokoll vermerkt.
    kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id, auffaelligkeit="Riss im Stoff")
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "wartungsfaellig", abzug=5)

    # Der Gegenstand muss vor der zweiten Ausleihe wieder verfügbar sein.
    kontext.gegenstand_repository.zustand_wechseln_atomar(
        gegenstand.id, "wartungsfaellig", "verfuegbar",
        kontext.gegenstand_repository.finden(gegenstand.id).version,
    )

    # Zweite Ausleihe: derselbe Schaden darf nicht erneut zugerechnet werden.
    zweite_ausleihe = kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    protokoll = kontext.rueckgabe_service.pruefung_abschliessen(
        gegenstand.id, "unauffaellig", abzug=5
    )

    assert protokoll.abzug == 0
    assert protokoll.schaden_vermerkt is False
    kaution_zweite = kontext.kaution_repository.finden_fuer_ausleihe(zweite_ausleihe.id)
    assert kaution_zweite.status == "freigegeben"
    assert kaution_zweite.betrag == 0


def test_teilabzug_verringert_den_verbleibenden_kautionssaldo(
    kontext: Anwendungskontext,
) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig", abzug=5)

    kaution_nachher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    assert kaution_nachher.status == "teilweise_einbehalten"
    assert kaution_nachher.betrag == kaution.betrag - 5


def test_unauffaellige_pruefung_protokolliert_die_vollstaendige_freigabe(
    kontext: Anwendungskontext,
) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    protokoll = kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    eintraege = kontext.audit_repository.alle_fuer(kaution.id)
    assert eintraege[-1]["referenz_id"] == kaution.id
    assert eintraege[-1]["betrag_oder_zustand"] == str(kaution.betrag)
    assert protokoll.id is not None


def _voller_zyklus(kontext: Anwendungskontext, gegenstand_id: str, mitglied_id: str, ergebnis: str):
    kontext.ausleihe_service.ausgeben(gegenstand_id, mitglied_id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand_id)
    return kontext.rueckgabe_service.pruefung_abschliessen(gegenstand_id, ergebnis)


def test_nutzungszaehler_erhoeht_sich_um_eins_je_unauffaelligem_zyklus_br_wa_01(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    _voller_zyklus(kontext, gegenstand.id, mitglied.id, "unauffaellig")
    gegenstand_nachher = kontext.gegenstand_repository.finden(gegenstand.id)

    assert gegenstand_nachher.nutzungszaehler == 1


def test_nutzungszaehler_erreicht_wartungsintervall_setzt_wartungsfaellig_br_wa_02(
    kontext: Anwendungskontext,
) -> None:
    kategorie = kontext.katalog_service.kategorie_anlegen("Zelt", 14, 5, False)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied = _mitglied(kontext)

    for _ in range(4):
        _voller_zyklus(kontext, gegenstand.id, mitglied.id, "unauffaellig")
    gegenstand_vor_fuenftem_zyklus = kontext.gegenstand_repository.finden(gegenstand.id)
    assert gegenstand_vor_fuenftem_zyklus.nutzungszaehler == 4

    _voller_zyklus(kontext, gegenstand.id, mitglied.id, "unauffaellig")
    gegenstand_nachher = kontext.gegenstand_repository.finden(gegenstand.id)

    assert gegenstand_nachher.nutzungszaehler == 5
    assert gegenstand_nachher.zustand == "wartungsfaellig"


def test_pruefung_rollt_ausleihe_und_kaution_bei_spaeterem_fehler_zurueck(
    kontext: Anwendungskontext, monkeypatch: pytest.MonkeyPatch
) -> None:
    gegenstand, ausleihe = _in_pruefung_mit_ausleihe(kontext)
    kaution_vorher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)

    def kaputt(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(kontext.vormerkung_service, "zuteilen", kaputt)

    with pytest.raises(RuntimeError):
        kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    assert kontext.ausleihe_repository.finden(ausleihe.id).status == "aktiv"
    assert kontext.gegenstand_repository.finden(gegenstand.id).zustand == "in_pruefung"
    kaution_nachher = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    assert kaution_nachher.status == kaution_vorher.status
    assert kaution_nachher.betrag == kaution_vorher.betrag
