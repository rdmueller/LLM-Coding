"""Issue 0014 (Wartung abschließen): BR-WA-03, BR-WA-04.
Issue 0015 (Gegenstand ausmustern): BR-VM-07.
"""
from __future__ import annotations

import sqlite3

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


def _wartungsfaellig(kontext: Anwendungskontext, inventarnummer="INV-100"):
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer=inventarnummer)
    mitglied = _mitglied(kontext)
    kontext.ausleihe_service.ausgeben(gegenstand.id, mitglied.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "wartungsfaellig")
    return kontext.gegenstand_repository.finden(gegenstand.id)


def test_wartung_abschliessen_setzt_zustand_und_zaehler_zurueck_br_wa_03(
    kontext: Anwendungskontext,
) -> None:
    gegenstand = _wartungsfaellig(kontext)

    ergebnis = kontext.wartung_service.wartung_abschliessen(gegenstand.id)

    assert ergebnis.zustand == "verfuegbar"
    assert ergebnis.nutzungszaehler == 0


def test_wartung_abschliessen_durch_falsche_rolle_wird_abgelehnt_br_wa_04(
    kontext: Anwendungskontext,
) -> None:
    gegenstand = _wartungsfaellig(kontext)

    with pytest.raises(ValidationError):
        kontext.wartung_service.wartung_abschliessen(gegenstand.id, rolle="thekendienst")


def test_wartung_abschliessen_nicht_wartungsfaelliger_gegenstand_wird_abgelehnt(
    kontext: Anwendungskontext,
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)

    with pytest.raises(ConflictError):
        kontext.wartung_service.wartung_abschliessen(gegenstand.id)


def test_wartung_abschliessen_unbekannter_gegenstand_wird_abgelehnt(
    kontext: Anwendungskontext,
) -> None:
    with pytest.raises(NotFoundError):
        kontext.wartung_service.wartung_abschliessen("unbekannt")


def test_wartung_abschliessen_mit_offener_vormerkung_ergibt_reserviert_br_vm_03(
    kontext: Anwendungskontext,
) -> None:
    gegenstand = _wartungsfaellig(kontext)
    kategorie_id = gegenstand.kategorie_id
    vormerker = _mitglied(kontext, "Nora")
    kontext.vormerkung_service.vormerken(kategorie_id, vormerker.id)

    kontext.wartung_service.wartung_abschliessen(gegenstand.id)

    ergebnis = kontext.gegenstand_repository.finden(gegenstand.id)
    assert ergebnis.zustand == "reserviert"
    reservierung = kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand.id)
    assert reservierung is not None
    assert reservierung.mitglied_id == vormerker.id


def test_ausmustern_laesst_vormerkungs_warteschlange_unveraendert_br_vm_07(
    kontext: Anwendungskontext, conn: sqlite3.Connection
) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)
    mitglied_a = _mitglied(kontext, "Karim")
    mitglied_b = _mitglied(kontext, "Nora")
    kontext.vormerkung_repository.anlegen(kategorie.id, mitglied_a.id, "2024-01-01T10:00:00")
    kontext.vormerkung_repository.anlegen(kategorie.id, mitglied_b.id, "2024-01-02T10:00:00")

    ergebnis = kontext.wartung_service.ausmustern(gegenstand.id)

    assert ergebnis.zustand == "ausgemustert"
    vormerkungen = conn.execute(
        "SELECT id FROM vormerkung WHERE kategorie_id = ?", (kategorie.id,)
    ).fetchall()
    assert len(vormerkungen) == 2
    ausleihen = conn.execute("SELECT id FROM ausleihe").fetchall()
    assert len(ausleihen) == 0


def test_wartung_abschliessen_rollt_bei_spaeterem_fehler_zurueck(
    kontext: Anwendungskontext, monkeypatch: pytest.MonkeyPatch
) -> None:
    gegenstand = _wartungsfaellig(kontext)

    def kaputt(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(kontext.vormerkung_service, "zuteilen", kaputt)

    with pytest.raises(RuntimeError):
        kontext.wartung_service.wartung_abschliessen(gegenstand.id)

    assert kontext.gegenstand_repository.finden(gegenstand.id).zustand == "wartungsfaellig"


def test_ausmustern_reservierten_gegenstand_wird_abgelehnt(kontext: Anwendungskontext) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id, inventarnummer="INV-res")
    ausleiher = _mitglied(kontext, "Karim")
    reservierendes_mitglied = _mitglied(kontext, "Fatima")
    kontext.ausleihe_service.ausgeben(gegenstand.id, ausleiher.id)
    kontext.rueckgabe_service.zuruecknehmen(gegenstand.id)
    kontext.vormerkung_service.vormerken(kategorie.id, reservierendes_mitglied.id)
    kontext.rueckgabe_service.pruefung_abschliessen(gegenstand.id, "unauffaellig")

    with pytest.raises(ConflictError):
        kontext.wartung_service.ausmustern(gegenstand.id)


def test_ausmustern_durch_falsche_rolle_wird_abgelehnt(kontext: Anwendungskontext) -> None:
    kategorie = _kategorie(kontext)
    gegenstand = _gegenstand(kontext, kategorie.id)

    with pytest.raises(ValidationError):
        kontext.wartung_service.ausmustern(gegenstand.id, rolle="thekendienst")


def test_ausmustern_unbekannter_gegenstand_wird_abgelehnt(kontext: Anwendungskontext) -> None:
    with pytest.raises(NotFoundError):
        kontext.wartung_service.ausmustern("unbekannt")
