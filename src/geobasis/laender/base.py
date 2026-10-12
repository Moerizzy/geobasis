"""Base class for a German state ("Land")."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING

from ..area import Area
from ..models import Product, Selection

if TYPE_CHECKING:  # pragma: no cover
    from ..download import DownloadResult


class Land:
    """A state with its product catalogue. Subclasses fill ``_products`` and
    implement administrative lookups (``_admin_area``)."""

    code: str = ""
    name: str = ""
    short: str = ""

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
        if gemeinde is not None:
            return self._admin_area("gemeinde", gemeinde)
        if kreis is not None:
            return self._admin_area("kreis", kreis)
        if regbez is not None:
            return self._admin_area("regbez", regbez)
        if bbox is not None:
            return Area.from_bbox(bbox, crs)
        if point is not None:
            return Area.from_point(point, radius, crs)
        return Area.from_geojson(geojson, crs)

    def _admin_area(self, level: str, query: str) -> Area:  # pragma: no cover
        raise NotImplementedError(f"{self.short}: Verwaltungseinheiten nicht verfügbar")

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
