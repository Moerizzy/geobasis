"""Nordrhein-Westfalen: Geobasis NRW via https://www.opengeodata.nrw.de."""

from __future__ import annotations

from ...geo import BBox
from ..base import Land
from . import grenzen, portal
from .dienste import SERVICES
from .products import LICENSE, LICENSE_URL, build_products


class NRW(Land):
    code = "nw"
    ags = "05"
    name = "Nordrhein-Westfalen"
    short = "NRW"
    license = LICENSE
    license_url = LICENSE_URL
    attribution = "Land NRW (Jahr), Datenlizenz Deutschland – Zero – Version 2.0"
    bbox = BBox(270_000, 5_570_000, 545_000, 5_830_000)
    boundaries = grenzen.provider
    portal = portal

    def __init__(self) -> None:
        super().__init__()
        self._products = {p.id: p for p in build_products()}

    def services(self) -> list[dict[str, str]]:
        return list(SERVICES)


nrw = NRW()
