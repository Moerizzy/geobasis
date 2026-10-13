"""Niedersachsen: LGLN open data via its STAC APIs."""

from __future__ import annotations

from ...geo import BBox
from ..base import Land
from . import grenzen
from .products import LICENSE, LICENSE_URL, build_products


class NI(Land):
    code = "ni"
    ags = "03"
    name = "Niedersachsen"
    short = "NI"
    license = LICENSE
    license_url = LICENSE_URL
    attribution = "Quelle: LGLN (Jahr), CC BY 4.0"
    bbox = BBox(310_000, 5_680_000, 700_000, 6_000_000)
    boundaries = grenzen.provider

    def __init__(self) -> None:
        super().__init__()
        self._products = {p.id: p for p in build_products()}


ni = NI()
