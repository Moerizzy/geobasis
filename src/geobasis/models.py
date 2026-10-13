"""Data model shared by all states: products, remote files and selections."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .geo import transformer

if TYPE_CHECKING:  # pragma: no cover
    from .area import Area
    from .download import DownloadResult


def format_size(n: float | None) -> str:
    """Human-readable size with German decimal comma: 1536 -> '1,5 kB'."""
    if n is None:
        return "?"
    units = ["B", "kB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1000 or u == units[-1]:
            s = f"{f:.0f}" if u == "B" else f"{f:.1f}"
            return f"{s.replace('.', ',')} {u}"
        f /= 1000
    return f"{n} B"  # pragma: no cover


@dataclass
class RemoteFile:
    """One downloadable file (or one WFS request) of a product."""

    name: str
    url: str
    size: int | None = None
    modified: str | None = None  # publication timestamp from the server
    product: str = ""
    crs: int | None = None
    bounds: tuple[float, float, float, float] | None = None  # in ``crs``
    key: str | None = None  # tile key ("280_5652") or AGS of an admin unit
    year: int | None = None
    date: str | None = None  # acquisition date from the tile metadata
    meta: dict[str, Any] = field(default_factory=dict)
    subdir: str = ""  # relative folder inside the product output folder
    post_data: bytes | None = None  # for WFS requests sent via POST
    land: str = ""  # state code, e.g. "nw"

    def footprint(self, dst: int = 4326) -> dict | None:
        """GeoJSON polygon of the tile outline in EPSG:``dst``."""
        if not self.bounds or self.crs is None:
            return None
        minx, miny, maxx, maxy = self.bounds
        fn = transformer(self.crs, dst)
        ring = [fn(minx, miny), fn(maxx, miny), fn(maxx, maxy), fn(minx, maxy)]
        ring.append(ring[0])
        return {"type": "Polygon", "coordinates": [[list(p) for p in ring]]}

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "post_data" and v not in (None, "", {})}
        if self.bounds:
            d["bounds"] = list(self.bounds)
        return d


class Selection(list):
    """List of :class:`RemoteFile` for one product and area, with helpers.

    A selection may span several states (see :func:`geobasis.find`); then
    ``products`` holds the product of every state involved and ``name`` is
    the product name the user asked for (used as output folder)."""

    def __init__(self, files: Iterable[RemoteFile] = (), product: Product | None = None,
                 area: Area | None = None, notes: list[str] | None = None,
                 products: list[Product] | None = None, name: str | None = None):
        super().__init__(files)
        self.product = product
        self.products: list[Product] = products or ([product] if product else [])
        self.area = area
        self.notes: list[str] = notes or []
        self.name = name or (product.id if product else "")

    @property
    def total_size(self) -> int:
        return sum(f.size or 0 for f in self)

    @property
    def unknown_sizes(self) -> int:
        return sum(1 for f in self if f.size is None)

    def summary(self) -> str:
        p = self.product
        if len(self.products) > 1:
            name = f"{self.name} ({', '.join(f'{q.land.upper()}: {q.title}' for q in self.products)})"
        else:
            name = f"{p.id} ({p.title})" if p else "?"
        where = f" für {self.area.label}" if self.area else " für das ganze Land"
        size = format_size(self.total_size)
        if self.unknown_sizes:
            size = f"{size} + unbekannt" if self.total_size else "Größe unbekannt"
        dates = sorted({f.date or str(f.year) for f in self if f.date or f.year})
        span = ""
        if dates:
            span = f", Stand {dates[0]}" if len(dates) == 1 else f", Stand {dates[0]} bis {dates[-1]}"
        per_land = ""
        lands = sorted({f.land for f in self if f.land})
        if len(lands) > 1:
            per_land = " (" + ", ".join(f"{lnd.upper()} {sum(1 for f in self if f.land == lnd)}"
                                       for lnd in lands) + ")"
        return f"{name}{where}: {len(self)} Datei(en){per_land}, {size}{span}"

    def to_geojson(self, dst: int = 4326) -> dict:
        feats = []
        for f in self:
            props = f.to_dict()
            props.pop("bounds", None)
            feats.append({"type": "Feature", "geometry": f.footprint(dst), "properties": props})
        return {"type": "FeatureCollection", "features": feats}

    def save_geojson(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_geojson(), ensure_ascii=False), "utf-8")
        return path

    def download(self, out: str | Path = ".", **kw) -> DownloadResult:
        from .download import download_selection

        return download_selection(self, out, **kw)

    def __repr__(self) -> str:
        return f"<Selection {self.summary()}>"


@dataclass
class Product:
    """A dataset of a state that geobasis knows how to find and download.

    Concrete states subclass this and implement :meth:`_find`.
    """

    id: str
    title: str
    category: str
    kind: str  # "tiles" | "admin" | "single" | "wfs"
    format: str = ""
    resolution: str = ""
    crs: str = "EPSG:25832"
    description: str = ""
    license: str = ""
    source: str = ""  # human-readable source URL
    variants: dict[str, str] = field(default_factory=dict)
    default_variant: str | None = None
    yearly: bool = False
    land: str = ""
    aliases: tuple[str, ...] = ()
    raster: bool = False  # GDAL-readable raster tiles (VRT possible)
    enumerable: bool = True  # False: listing the whole state is too expensive

    # --- public API ---------------------------------------------------------
    def find(self, area: Area | None = None, *, year: int | None = None,
             variant: str | None = None, latest: bool = True,
             with_meta: bool = True) -> Selection:
        if self.yearly and year is None:
            raise ValueError(f"'{self.id}' ist ein Archivprodukt: bitte ein Jahr angeben "
                             f"(verfügbar: {', '.join(map(str, self.years()))})")
        if variant is not None and variant not in self.variants:
            raise ValueError(f"Unbekannte Variante {variant!r} für '{self.id}' "
                             f"(verfügbar: {', '.join(self.variants) or 'keine'})")
        files = self._find(area, year=year, variant=variant or self.default_variant,
                           latest=latest, with_meta=with_meta)
        for f in files:
            f.land = f.land or self.land
        return files

    def years(self) -> list[int]:
        return []

    def coverage(self, area: Area | None = None, workers: int = 4) -> dict[int, int]:
        """For archive products: number of files per year touching the area."""
        if not self.yearly:
            raise ValueError(f"'{self.id}' ist kein Archivprodukt")
        from concurrent.futures import ThreadPoolExecutor

        def count(y: int) -> tuple[int, int]:
            return y, len(self._find(area, year=y, variant=self.default_variant, latest=True,
                                     with_meta=False))

        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            return dict(sorted(ex.map(count, self.years())))

    def download(self, area: Area | None = None, out: str | Path = ".", *,
                 year: int | None = None, variant: str | None = None,
                 latest: bool = True, **kw) -> DownloadResult:
        return self.find(area, year=year, variant=variant, latest=latest).download(out, **kw)

    def _find(self, area: Area | None, **opts) -> Selection:  # pragma: no cover
        raise NotImplementedError

    def info(self) -> dict[str, Any]:
        d = {
            "id": self.id, "land": self.land.upper(), "titel": self.title, "kategorie": self.category,
            "art": {"tiles": "Kacheln", "admin": "je Verwaltungseinheit", "single": "eine Datei",
                    "wfs": "Ausschnitt per WFS"}.get(self.kind, self.kind),
            "format": self.format, "aufloesung": self.resolution, "crs": self.crs,
            "lizenz": self.license, "quelle": self.source, "beschreibung": self.description,
        }
        if self.variants:
            d["varianten"] = list(self.variants)
            d["standardvariante"] = self.default_variant
        if self.yearly:
            d["archiv"] = True
        return {k: v for k, v in d.items() if v not in ("", None, [])}

    def __str__(self) -> str:
        return f"{self.id}: {self.title}"
