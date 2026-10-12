"""Areas of interest: where should data be fetched for?

An :class:`Area` is a :class:`~geobasis.geo.Shape` in EPSG:25832 plus a
human-readable label. Areas can be built from a bounding box, a point with
radius, a GeoJSON file/object, or - through a state module - from the
name or key (AGS) of a municipality, district or administrative region.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .geo import Shape, guess_crs, parse_crs

WORK_CRS = 25832


@dataclass
class Area:
    shape: Shape  # always EPSG:25832
    label: str
    ags: str | None = None  # official key if the area is an admin unit
    level: str | None = None  # "gemeinde" | "kreis" | "regbez"

    def __post_init__(self):
        if self.shape.crs != WORK_CRS:
            self.shape = self.shape.transform(WORK_CRS)

    @classmethod
    def from_bbox(cls, bbox: Sequence[float] | str, crs: str | int | None = None) -> Area:
        """``bbox`` = (minx, miny, maxx, maxy) or "minx,miny,maxx,maxy".

        Without ``crs`` the system is guessed: degrees -> WGS84 (lon/lat),
        metres -> ETRS89/UTM32."""
        vals = _floats(bbox, 4, "bbox")
        minx, miny, maxx, maxy = vals
        if minx > maxx or miny > maxy:
            raise ValueError("bbox erwartet minx,miny,maxx,maxy (bei Grad: Länge,Breite,Länge,Breite)")
        code = parse_crs(crs) or guess_crs(minx, miny)
        _check_lonlat_order(code, minx, miny)
        shape = Shape.from_bbox(minx, miny, maxx, maxy, crs=code)
        label = f"Box {_fmt(vals)}" + ("" if code == WORK_CRS else f" (EPSG:{code})")
        return cls(shape, label)

    @classmethod
    def from_point(cls, point: Sequence[float] | str, radius: float = 0.0,
                   crs: str | int | None = None) -> Area:
        """Point (lon, lat or easting, northing) with optional radius in metres."""
        x, y = _floats(point, 2, "punkt")
        code = parse_crs(crs) or guess_crs(x, y)
        _check_lonlat_order(code, x, y)
        px, py = Shape(lines=[[(x, y), (x, y)]], crs=code).transform(WORK_CRS).lines[0][0]
        shape = Shape.circle(px, py, float(radius))
        r = f", Radius {radius:g} m" if radius else ""
        return cls(shape, f"Punkt {_fmt((x, y))}{r}")

    @classmethod
    def from_geojson(cls, src: str | Path | dict, crs: str | int | None = None) -> Area:
        """GeoJSON as dict, JSON string or path to a .geojson/.json file."""
        label = "GeoJSON"
        if isinstance(src, dict):
            obj = src
        else:
            s = str(src)
            if s.lstrip().startswith("{"):
                obj = json.loads(s)
            else:
                path = Path(s)
                obj = json.loads(path.read_text("utf-8"))
                label = path.name
        shape = Shape.from_geojson(obj, crs=parse_crs(crs))
        return cls(shape, label)

    @property
    def bbox(self):
        return self.shape.bbox

    def __repr__(self) -> str:
        return f"<Area {self.label}: {self.shape!r}>"


def _floats(v: Sequence[float] | str, n: int, what: str) -> list[float]:
    if isinstance(v, str):
        v = [p for p in v.replace(";", ",").replace(" ", ",").split(",") if p]
    vals = [float(x) for x in v]
    if len(vals) != n:
        raise ValueError(f"{what} erwartet {n} Zahlen, bekommen: {v!r}")
    return vals


def _check_lonlat_order(code: int, x: float, y: float) -> None:
    # Germany: lon 5..16, lat 47..56 - catch swapped lat/lon early
    if code in (4326, 4258) and 47 <= x <= 56 and 5 <= y <= 16:
        raise ValueError("Koordinaten sehen vertauscht aus: bitte Länge (lon) vor Breite (lat) "
                         f"angeben, z. B. {y},{x}")


def _fmt(vals: Sequence[float]) -> str:
    return ",".join(f"{v:.0f}" if abs(v) >= 1000 else f"{v:g}" for v in vals)
