"""FastAPI-Anwendung (ADR-0001). Controller mappen explizit auf/von DTOs (ADR-0003)."""
from __future__ import annotations

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app.container import Anwendungskontext, erstellen
from app.db import get_connection, init_db
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Ausleihe, Gegenstand, Kategorie, Mitglied
from app.api.schemas import (
    AusgabeRequest,
    AusleiheResponse,
    EinweisungAnlegenRequest,
    EinweisungResponse,
    GegenstandAnlegenRequest,
    GegenstandResponse,
    KategorieAnlegenRequest,
    KategorieResponse,
    MitgliedAnlegenRequest,
    MitgliedResponse,
    RuecknahmeRequest,
    VerfuegbarkeitResponse,
    VormerkungAnlegenRequest,
    VormerkungResponse,
)


class RolleNichtErlaubtError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="Leihgut-Verwaltung")

    init_conn = get_connection(db_path)
    init_db(init_conn)
    init_conn.close()
    app.state.db_path = db_path

    def hole_kontext() -> Anwendungskontext:
        conn = get_connection(db_path)
        try:
            yield erstellen(conn)
        finally:
            conn.close()

    def rolle_pruefen(erlaubte_rollen: set[str]):
        def dependency(x_rolle: str | None = Header(default=None)) -> str:
            if x_rolle not in erlaubte_rollen:
                raise RolleNichtErlaubtError(f"Rolle '{x_rolle}' ist für diese Aktion nicht erlaubt")
            return x_rolle

        return dependency

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"code": exc.code, "message": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": exc.code, "message": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        status_code = 403 if exc.code == "FORBIDDEN" else 422
        return JSONResponse(status_code=status_code, content={"code": exc.code, "message": str(exc)})

    @app.exception_handler(RolleNichtErlaubtError)
    async def rolle_handler(request: Request, exc: RolleNichtErlaubtError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"code": "FORBIDDEN", "message": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/kategorien", response_model=KategorieResponse, status_code=201)
    def kategorie_anlegen(
        body: KategorieAnlegenRequest, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> KategorieResponse:
        kategorie = kontext.katalog_service.kategorie_anlegen(
            body.name, body.leihdauerTage, body.wartungsintervall, body.einweisungspflichtig
        )
        return _zu_kategorie_response(kategorie)

    @app.get("/kategorien/{kategorie_id}", response_model=KategorieResponse)
    def kategorie_lesen(
        kategorie_id: str, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> KategorieResponse:
        return _zu_kategorie_response(kontext.katalog_service.kategorie_lesen(kategorie_id))

    @app.post("/gegenstaende", response_model=GegenstandResponse, status_code=201)
    def gegenstand_anlegen(
        body: GegenstandAnlegenRequest, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> GegenstandResponse:
        gegenstand = kontext.katalog_service.gegenstand_anlegen(
            body.inventarnummer, body.kategorieId, body.wiederbeschaffungswert
        )
        return _zu_gegenstand_response(gegenstand)

    @app.get("/gegenstaende/{gegenstand_id}", response_model=GegenstandResponse)
    def gegenstand_lesen(
        gegenstand_id: str, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> GegenstandResponse:
        gegenstand = kontext.katalog_service.gegenstand_lesen(gegenstand_id)
        antwort = _zu_gegenstand_response(gegenstand)
        if gegenstand.zustand == "ausgeliehen":
            ausleihe = kontext.ausleihe_repository.finden_aktive_fuer_gegenstand(gegenstand_id)
            if ausleihe is not None:
                antwort.rueckgabefrist = ausleihe.rueckgabefrist
        elif gegenstand.zustand == "reserviert":
            reservierung = kontext.reservierung_repository.finden_aktiv_fuer_gegenstand(gegenstand_id)
            if reservierung is not None:
                antwort.reserviertFuerMitgliedId = reservierung.mitglied_id
        return antwort

    @app.post("/mitglieder", response_model=MitgliedResponse, status_code=201)
    def mitglied_anlegen(
        body: MitgliedAnlegenRequest, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> MitgliedResponse:
        mitglied = kontext.mitglied_service.mitglied_anlegen(body.name)
        return _zu_mitglied_response(mitglied, kontext)

    @app.get("/mitglieder/{mitglied_id}", response_model=MitgliedResponse)
    def mitglied_lesen(
        mitglied_id: str, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> MitgliedResponse:
        return _zu_mitglied_response(kontext.mitglied_service.mitglied_lesen(mitglied_id), kontext)

    @app.post("/mitglieder/{mitglied_id}/einweisungen", response_model=EinweisungResponse, status_code=201)
    def einweisung_anlegen(
        mitglied_id: str,
        body: EinweisungAnlegenRequest,
        kontext: Anwendungskontext = Depends(hole_kontext),
    ):
        einweisung = kontext.mitglied_service.einweisung_erfassen(mitglied_id, body.kategorieId)
        return EinweisungResponse(
            id=einweisung.id,
            mitgliedId=einweisung.mitglied_id,
            kategorieId=einweisung.kategorie_id,
            datum=einweisung.datum,
        )

    @app.post(
        "/gegenstaende/{gegenstand_id}/ausgabe",
        response_model=AusleiheResponse,
        status_code=201,
        dependencies=[Depends(rolle_pruefen({"thekendienst"}))],
    )
    def gegenstand_ausgeben(
        gegenstand_id: str,
        body: AusgabeRequest,
        kontext: Anwendungskontext = Depends(hole_kontext),
    ):
        ausleihe = kontext.ausleihe_service.ausgeben(gegenstand_id, body.mitgliedId)
        return _zu_ausleihe_response(ausleihe, kontext)

    @app.post(
        "/ausleihen/{ausleihe_id}/verlaengerung",
        response_model=AusleiheResponse,
    )
    def ausleihe_verlaengern(
        ausleihe_id: str,
        x_rolle: str = Depends(rolle_pruefen({"thekendienst", "mitglied"})),
        x_mitglied_id: str | None = Header(default=None),
        kontext: Anwendungskontext = Depends(hole_kontext),
    ):
        if x_rolle == "mitglied" and x_mitglied_id is None:
            raise ValidationError("Mitgliedsrolle erfordert den Header 'X-Mitglied-Id'", code="FORBIDDEN")
        ausleihe = kontext.ausleihe_service.verlaengern(
            ausleihe_id, anfragendes_mitglied_id=x_mitglied_id if x_rolle == "mitglied" else None
        )
        return _zu_ausleihe_response(ausleihe, kontext)

    @app.post(
        "/gegenstaende/{gegenstand_id}/ruecknahme",
        response_model=GegenstandResponse,
        status_code=200,
        dependencies=[Depends(rolle_pruefen({"thekendienst"}))],
    )
    def gegenstand_zuruecknehmen(
        gegenstand_id: str,
        body: RuecknahmeRequest,
        kontext: Anwendungskontext = Depends(hole_kontext),
    ):
        gegenstand = kontext.rueckgabe_service.zuruecknehmen(gegenstand_id, body.auffaelligkeit)
        return _zu_gegenstand_response(gegenstand)

    @app.post(
        "/kategorien/{kategorie_id}/vormerkungen",
        response_model=VormerkungResponse,
        status_code=201,
        dependencies=[Depends(rolle_pruefen({"mitglied", "thekendienst"}))],
    )
    def vormerkung_anlegen(
        kategorie_id: str,
        body: VormerkungAnlegenRequest,
        kontext: Anwendungskontext = Depends(hole_kontext),
    ):
        vormerkung, position = kontext.vormerkung_service.vormerken(kategorie_id, body.mitgliedId)
        return VormerkungResponse(
            id=vormerkung.id,
            kategorieId=vormerkung.kategorie_id,
            mitgliedId=vormerkung.mitglied_id,
            position=position,
        )

    @app.get("/kategorien/{kategorie_id}/verfuegbarkeit", response_model=VerfuegbarkeitResponse)
    def kategorie_verfuegbarkeit(
        kategorie_id: str, kontext: Anwendungskontext = Depends(hole_kontext)
    ) -> VerfuegbarkeitResponse:
        verfuegbarkeit = kontext.katalog_service.verfuegbarkeit(kategorie_id)
        return VerfuegbarkeitResponse(
            anzahlVerfuegbar=verfuegbarkeit.anzahl_verfuegbar,
            warteschlangenlaenge=verfuegbarkeit.warteschlangenlaenge,
        )

    return app


def _zu_kategorie_response(kategorie: Kategorie) -> KategorieResponse:
    return KategorieResponse(
        id=kategorie.id,
        name=kategorie.name,
        leihdauerTage=kategorie.leihdauer_tage,
        wartungsintervall=kategorie.wartungsintervall,
        einweisungspflichtig=kategorie.einweisungspflichtig,
    )


def _zu_gegenstand_response(gegenstand: Gegenstand) -> GegenstandResponse:
    return GegenstandResponse(
        id=gegenstand.id,
        inventarnummer=gegenstand.inventarnummer,
        kategorieId=gegenstand.kategorie_id,
        wiederbeschaffungswert=gegenstand.wiederbeschaffungswert,
        kaution=gegenstand.kaution,
        nutzungszaehler=gegenstand.nutzungszaehler,
        zustand=gegenstand.zustand,
    )


def _zu_mitglied_response(mitglied: Mitglied, kontext: Anwendungskontext) -> MitgliedResponse:
    gesperrt = kontext.mitglied_service.ist_gesperrt(mitglied.id)  # BR-SP-01 (abgeleitet)
    return MitgliedResponse(id=mitglied.id, name=mitglied.name, gesperrt=gesperrt)


def _zu_ausleihe_response(ausleihe: Ausleihe, kontext: Anwendungskontext) -> AusleiheResponse:
    kaution = kontext.kaution_repository.finden_fuer_ausleihe(ausleihe.id)
    return AusleiheResponse(
        id=ausleihe.id,
        gegenstandId=ausleihe.gegenstand_id,
        mitgliedId=ausleihe.mitglied_id,
        ausgabedatum=ausleihe.ausgabedatum,
        rueckgabefrist=ausleihe.rueckgabefrist,
        verlaengert=ausleihe.verlaengert,
        kaution=kaution.betrag if kaution is not None else 0,
    )
