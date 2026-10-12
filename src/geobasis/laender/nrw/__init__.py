"""Nordrhein-Westfalen: Geobasis NRW via https://www.opengeodata.nrw.de."""

from __future__ import annotations

from ...area import Area
from ..base import Land
from . import grenzen, portal
from .dienste import SERVICES
from .products import LICENSE, LICENSE_URL, build_products


class NRW(Land):
    code = "nw"
    name = "Nordrhein-Westfalen"
    short = "NRW"
    license = LICENSE
    license_url = LICENSE_URL
    attribution = "Land NRW (Jahr), Datenlizenz Deutschland – Zero – Version 2.0"
    portal = portal

    def __init__(self) -> None:
        super().__init__()
        self._products = {p.id: p for p in build_products()}

    def _admin_area(self, level: str, query: str) -> Area:
        return grenzen.area(level, query)

    def gemeinden(self, suche: str | None = None) -> list[grenzen.Unit]:
        return _filter(grenzen.units("gemeinde"), suche)

    def kreise(self, suche: str | None = None) -> list[grenzen.Unit]:
        return _filter(grenzen.units("kreis"), suche)

    def regierungsbezirke(self, suche: str | None = None) -> list[grenzen.Unit]:
        return _filter(grenzen.units("regbez"), suche)

    def services(self) -> list[dict[str, str]]:
        return list(SERVICES)


def _filter(units: list[grenzen.Unit], suche: str | None) -> list[grenzen.Unit]:
    if not suche:
        return units
    q = grenzen._norm(suche)
    return [u for u in units if q in grenzen._norm(u.name) or u.ags.startswith(suche.strip())]


nrw = NRW()
