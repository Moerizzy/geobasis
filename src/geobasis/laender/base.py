"""Base class for a German state ("Land")."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING

from ..area import Area
from ..geo import BBox
from ..models import Product, Selection

if TYPE_CHECKING:  # pragma: no cover
    from ..download import DownloadResult
    from ..grenzen import BoundaryProvider, Unit


class Land:
    """A state with its product catalogue and administrative units."""

    code: str = ""  # two letters, e.g. "nw"
    ags: str = ""  # state key, first two digits of every AGS, e.g. "05"
    name: str = ""
    short: str = ""
    license: str = ""
    license_url: str = ""
    attribution: str = ""
    bbox: BBox | None = None  # rough extent in EPSG:25832, for routing queries
    boundaries: BoundaryProvider | None = None
    portal = None  # optional browser for an open-data portal

    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    # -- catalogue -----------------------------------------------------------
    def products(self, category: str | None = None) -> list[Product]:
        ps = list(self._products.values())
        if category:
            c = category.lower()
            ps = [p for p in ps if c in p.category.lower()]
        return ps

    def categories(self) -> list[str]:
        seen: list[str] = []
        for p in self._products.values():
            if p.category not in seen:
                seen.append(p.category)
        return seen

    def has_product(self, product_id: str) -> bool:
        try:
            self.product(product_id)
            return True
        except KeyError:
            return False

    def product(self, product_id: str | Product) -> Product:
        if isinstance(product_id, Product):
            return product_id
        pid = product_id.strip().lower()
        if pid in self._products:
            return self._products[pid]
        for p in self._products.values():
            if pid in p.aliases:
                return p
        names = list(self._products) + [a for p in self._products.values() for a in p.aliases]
        close = difflib.get_close_matches(pid, names, n=4, cutoff=0.5)
        hint = f" Meinten Sie: {', '.join(close)}?" if close else ""
        raise KeyError(f"Produkt {product_id!r} gibt es für {self.short} nicht.{hint} "
                       "Alle Produkte: geobasis produkte")

    # -- areas ---------------------------------------------------------------
    def area(self, *, area: Area | None = None, gemeinde: str | None = None,
             kreis: str | None = None, regbez: str | None = None,
             bbox=None, point=None, radius: float = 0.0, geojson=None,
             crs: str | int | None = None) -> Area | None:
        """Build an :class:`Area` from exactly one of the keyword arguments."""
        given = {k: v for k, v in dict(area=area, gemeinde=gemeinde, kreis=kreis, regbez=regbez,
                                       bbox=bbox, point=point, geojson=geojson).items()
                 if v is not None}
        if len(given) > 1:
            raise ValueError(f"Bitte nur eine Gebietsangabe verwenden, nicht {', '.join(given)}")
        if not given:
            return None
        if area is not None:
            return area
        for level, query in (("gemeinde", gemeinde), ("kreis", kreis), ("regbez", regbez)):
            if query is not None:
                return self.admin_area(level, query)
        if bbox is not None:
            return Area.from_bbox(bbox, crs)
        if point is not None:
            return Area.from_point(point, radius, crs)
        return Area.from_geojson(geojson, crs)

    def admin_area(self, level: str, query: str) -> Area:
        if self.boundaries is None:
            raise LookupError(f"{self.short}: Verwaltungseinheiten sind nicht verfügbar")
        return self.boundaries.area(level, query)

    def _units(self, level: str, suche: str | None) -> list[Unit]:
        if self.boundaries is None or level not in self.boundaries.levels:
            return []
        return self.boundaries.search(level, suche)

    def gemeinden(self, suche: str | None = None) -> list[Unit]:
        return self._units("gemeinde", suche)

    def kreise(self, suche: str | None = None) -> list[Unit]:
        return self._units("kreis", suche)

    def regierungsbezirke(self, suche: str | None = None) -> list[Unit]:
        return self._units("regbez", suche)

    def services(self) -> list[dict[str, str]]:
        return []

    # -- convenience -----------------------------------------------------------
    def find(self, product: str | Product, *, year: int | None = None,
             variant: str | None = None, latest: bool = True, with_meta: bool = True,
             **area_kw) -> Selection:
        """Files of ``product`` for an area, e.g. ``find("dgm1", gemeinde="Münster")``."""
        p = self.product(product)
        return p.find(self.area(**area_kw), year=year, variant=variant, latest=latest,
                      with_meta=with_meta)

    def download(self, product: str | Product, out: str | Path = ".", *,
                 year: int | None = None, variant: str | None = None, latest: bool = True,
                 workers: int = 4, overwrite: bool = False, progress: bool = True,
                 vrt: bool = False, extract: bool = False, **area_kw) -> DownloadResult:
        """Find and download in one step; returns a :class:`DownloadResult`."""
        sel = self.find(product, year=year, variant=variant, latest=latest, **area_kw)
        return sel.download(out, workers=workers, overwrite=overwrite, progress=progress,
                            vrt=vrt, extract=extract)

    def __repr__(self) -> str:
        return f"<Land {self.short}: {len(self._products)} Produkte>"
