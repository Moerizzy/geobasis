"""Products of Niedersachsen, served by the STAC APIs of the LGLN."""

from __future__ import annotations

import posixpath
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ... import http
from ...geo import ShapeIndex, transformer
from ...models import Product, RemoteFile, Selection
from ...tiles import parse_tile, parse_year
from . import stac

LICENSE = "Creative Commons Namensnennung 4.0 (CC BY 4.0)"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/deed.de"
HEAD_LIMIT = 2000  # look up file sizes only for selections up to this size
HM, LB = "Höhenmodelle", "Luftbilder"


@dataclass
class StacProduct(Product):
    """Tiles from a STAC collection. ``prefix`` selects items by their id,
    ``variants`` choose between data assets (e.g. RGB or RGBI)."""

    service: str = ""
    collection: str = ""
    prefix: str = ""

    def __post_init__(self):
        self.land = "ni"
        self.kind = "tiles"
        self.license = self.license or LICENSE
        self.enumerable = False
        if not self.source:
            self.source = f"{stac.ENDPOINTS[self.service]}/collections/{self.collection}"

    def years(self) -> list[int]:
        if not self.yearly:
            return []
        iv = stac.collection(self.service, self.collection)["extent"]["temporal"]["interval"][0]
        start, end = int(iv[0][:4]), int((iv[1] or iv[0])[:4])
        return list(range(start, end + 1))

    def _asset(self, item: dict, variant: str | None) -> dict | None:
        data = [(k, a) for k, a in (item.get("assets") or {}).items()
                if "data" in (a.get("roles") or []) and a.get("href")]
        if variant:
            def matches(k: str, a: dict) -> bool:
                text = (k + " " + posixpath.basename(urllib.parse.urlsplit(a["href"]).path)).lower()
                if variant == "rgb":
                    return "rgb" in text and "rgbi" not in text
                return variant in text
            data = [(k, a) for k, a in data if matches(k, a)]
        return data[0][1] if data else None

    def _find(self, area, *, year, variant, latest, with_meta) -> Selection:
        bbox = None
        if area is not None:
            b = area.shape.transform(4326).bbox.buffer(0.0005)
            bbox = b.as_tuple()
        dt = f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z" if year else None
        idx = ShapeIndex(area.shape) if area is not None else None
        to_utm = transformer(4326, 25832)
        out: list[RemoteFile] = []
        for item in stac.items(self.service, self.collection, bbox=bbox, datetime=dt):
            iid = item.get("id", "")
            if self.prefix and not iid.startswith(self.prefix):
                continue
            asset = self._asset(item, variant)
            if asset is None:
                continue
            ref = parse_tile(iid, 25832)
            if ref is not None:
                bounds = ref.bounds()
                key = ref.key
            else:  # fall back to the WGS84 bbox of the item
                x0, y0, x1, y1 = item["bbox"][:4]
                (ax, ay), (bx, by) = to_utm(x0, y0), to_utm(x1, y1)
                bounds, key = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)), iid
            if idx is not None and not idx.intersects_rect(*bounds):
                continue
            props = item.get("properties") or {}
            date = (props.get("datetime") or "")[:10] or None
            href = asset["href"]
            out.append(RemoteFile(
                name=posixpath.basename(urllib.parse.urlsplit(href).path), url=href,
                size=asset.get("file:size"), product=self.id, crs=25832, bounds=bounds, key=key,
                year=int(date[:4]) if date else parse_year(iid), date=date,
                meta={k: str(v) for k, v in props.items() if v not in (None, "") and k != "datetime"},
                subdir=str(year) if self.yearly and year else ""))
        if latest:
            best: dict[str, RemoteFile] = {}
            for f in out:
                cur = best.get(f.key or f.name)
                if cur is None or (f.date or "", f.name) > (cur.date or "", cur.name):
                    best[f.key or f.name] = f
            out = list(best.values())
        out.sort(key=lambda r: (r.key or "", r.date or "", r.name))
        notes = []
        if with_meta and out:
            missing = [f for f in out if f.size is None]
            if len(missing) <= HEAD_LIMIT:
                with ThreadPoolExecutor(max_workers=8) as ex:
                    for f, size in zip(missing, ex.map(lambda f: http.head_size(f.url), missing)):
                        f.size = size
            else:
                notes.append(f"Dateigrößen nicht ermittelt (mehr als {HEAD_LIMIT} Dateien).")
        return Selection(out, self, area, notes)


def build_products() -> list[Product]:
    return [
        StacProduct("dgm1", "Digitales Geländemodell 1 m (DGM1)", HM, "tiles",
                    "Cloud-Optimized GeoTIFF", "1 m", raster=True,
                    description="Höhe der Erdoberfläche ohne Bewuchs und Bebauung, 1-km-Kacheln.",
                    service="dgm", collection="dgm1", prefix="dgm1",
                    aliases=("dgm", "gelaendemodell")),
        StacProduct("dom1", "Digitales Oberflächenmodell 1 m (DOM1)", HM, "tiles",
                    "Cloud-Optimized GeoTIFF", "1 m", raster=True,
                    description="Höhe der Oberfläche inklusive Gebäude und Vegetation, 1-km-Kacheln.",
                    service="dom", collection="dom1", prefix="dom1", aliases=("dom",)),
        StacProduct("bdom20", "Bildbasiertes Oberflächenmodell 20 cm (bDOM20)", HM, "tiles",
                    "Cloud-Optimized GeoTIFF", "0,2 m", raster=True,
                    description="Aus Luftbildern abgeleitetes Oberflächenmodell, 1-km-Kacheln.",
                    service="bdom", collection="BDOM", prefix="bdom20", aliases=("bdom",)),
        StacProduct("dop20", "Digitale Orthophotos 20 cm (DOP20)", LB, "tiles",
                    "Cloud-Optimized GeoTIFF", "0,2 m", raster=True,
                    description="Landesweite Luftbilder, 2-km-Kacheln. Standard: Farbe (RGB, ca. 25 MB "
                                "je Kachel); Variante rgbi mit Infrarot ist unkomprimiert (565 MB).",
                    service="dop", collection="DOP", prefix="dop20",
                    variants={"rgb": "rgb", "rgbi": "rgbi"}, default_variant="rgb",
                    aliases=("dop", "luftbild", "orthophoto")),
        StacProduct("dop10", "Digitale Orthophotos 10 cm (DOP10, neue Befliegungen)", LB, "tiles",
                    "Cloud-Optimized GeoTIFF", "0,1 m", raster=True,
                    description="Hoch aufgelöste Luftbilder aus den jüngsten Bildflügen, 1-km-Kacheln; "
                                "noch nicht landesweit. Varianten wie DOP20.",
                    service="dop", collection="DOP", prefix="dop10",
                    variants={"rgb": "rgb", "rgbi": "rgbi"}, default_variant="rgb"),
        StacProduct("dop-hist", "Historische Orthophotos 20 cm (Luftbildarchiv)", LB, "tiles",
                    "Cloud-Optimized GeoTIFF", "0,2 m", raster=True, yearly=True,
                    description="Alle Jahrgänge der DOP20; Abdeckung je Jahrgang unterschiedlich.",
                    service="dop", collection="DOP", prefix="dop20",
                    variants={"rgb": "rgb", "rgbi": "rgbi"}, default_variant="rgb",
                    aliases=("dop_hist", "luftbildarchiv", "historisch")),
    ]
