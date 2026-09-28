"""Pydantic-DTOs für die REST-Schnittstelle (ADR-0001: Validierung an der REST-Grenze)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class KategorieAnlegenRequest(BaseModel):
    name: str = Field(min_length=1)
    leihdauerTage: int = Field(gt=0)
    wartungsintervall: int = Field(gt=0)
    einweisungspflichtig: bool = False


class KategorieResponse(BaseModel):
    id: str
    name: str
    leihdauerTage: int
    wartungsintervall: int
    einweisungspflichtig: bool


class GegenstandAnlegenRequest(BaseModel):
    inventarnummer: str
    kategorieId: str
    wiederbeschaffungswert: float = Field(gt=0)


class GegenstandResponse(BaseModel):
    id: str
    inventarnummer: str
    kategorieId: str
    wiederbeschaffungswert: float
    kaution: int
    nutzungszaehler: int
    zustand: str
    rueckgabefrist: str | None = None
    reserviertFuerMitgliedId: str | None = None


class MitgliedAnlegenRequest(BaseModel):
    name: str = Field(min_length=1)


class MitgliedResponse(BaseModel):
    id: str
    name: str
    gesperrt: bool


class EinweisungAnlegenRequest(BaseModel):
    kategorieId: str = Field(min_length=1)


class EinweisungResponse(BaseModel):
    id: str
    mitgliedId: str
    kategorieId: str
    datum: str


class AusgabeRequest(BaseModel):
    mitgliedId: str = Field(min_length=1)


class RuecknahmeRequest(BaseModel):
    auffaelligkeit: str | None = None


class AusleiheResponse(BaseModel):
    id: str
    gegenstandId: str
    mitgliedId: str
    ausgabedatum: str
    rueckgabefrist: str
    verlaengert: bool
    kaution: int


class FehlerResponse(BaseModel):
    code: str
    message: str


class VormerkungAnlegenRequest(BaseModel):
    mitgliedId: str = Field(min_length=1)


class VormerkungResponse(BaseModel):
    id: str
    kategorieId: str
    mitgliedId: str
    position: int


class VerfuegbarkeitResponse(BaseModel):
    anzahlVerfuegbar: int
    warteschlangenlaenge: int
