"""Geometry and coordinate helpers without third-party dependencies.

Everything inside geobasis works in metric, projected coordinates
(ETRS89 / UTM zone 32N, EPSG:25832, the CRS of almost all German state
geodata in the west). This module provides

* forward/inverse Transverse Mercator (Krüger series, sub-millimetre inside
  a zone) for UTM and the historic Gauß-Krüger zones,
* a 7-parameter Helmert shift between DHDN (Bessel) and ETRS89, accurate to
  a few metres, which is plenty for selecting tiles,
* :class:`Shape`, a light-weight (multi)polygon/line container, and
  :class:`ShapeIndex`, which answers "does this rectangle touch the shape?"
  quickly even for administrative boundaries with thousands of vertices.

pyproj or shapely are deliberately not required: the package must install
anywhere with nothing but the standard library.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

Point = tuple[float, float]
Ring = list[Point]

# --------------------------------------------------------------------------
# Ellipsoids and Transverse Mercator
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Ellipsoid:
    a: float
    f: float

    @property
    def e2(self) -> float:
        return self.f * (2.0 - self.f)


GRS80 = Ellipsoid(6378137.0, 1 / 298.257222101)
BESSEL = Ellipsoid(6377397.155, 1 / 299.1528128)


class TransverseMercator:
    """Transverse Mercator after Krüger/Karney (6th order in n)."""

    def __init__(self, ell: Ellipsoid, lon0: float, k0: float,
                 false_easting: float, false_northing: float = 0.0):
        self.ell = ell
        self.lon0 = math.radians(lon0)
        self.k0 = k0
        self.fe = false_easting
        self.fn = false_northing
        n = ell.f / (2.0 - ell.f)
        n2, n3, n4, n5, n6 = n**2, n**3, n**4, n**5, n**6
        self.e = math.sqrt(ell.e2)
        self.A = ell.a / (1 + n) * (1 + n2 / 4 + n4 / 64 + n6 / 256)
        self.alpha = (
            n / 2 - 2 * n2 / 3 + 5 * n3 / 16 + 41 * n4 / 180 - 127 * n5 / 288 + 7891 * n6 / 37800,
            13 * n2 / 48 - 3 * n3 / 5 + 557 * n4 / 1440 + 281 * n5 / 630 - 1983433 * n6 / 1935360,
            61 * n3 / 240 - 103 * n4 / 140 + 15061 * n5 / 26880 + 167603 * n6 / 181440,
            49561 * n4 / 161280 - 179 * n5 / 168 + 6601661 * n6 / 7257600,
            34729 * n5 / 80640 - 3418889 * n6 / 1995840,
            212378941 * n6 / 319334400,
        )
        self.beta = (
            n / 2 - 2 * n2 / 3 + 37 * n3 / 96 - n4 / 360 - 81 * n5 / 512 + 96199 * n6 / 604800,
            n2 / 48 + n3 / 15 - 437 * n4 / 1440 + 46 * n5 / 105 - 1118711 * n6 / 3870720,
            17 * n3 / 480 - 37 * n4 / 840 - 209 * n5 / 4480 + 5569 * n6 / 90720,
            4397 * n4 / 161280 - 11 * n5 / 504 - 830251 * n6 / 7257600,
            4583 * n5 / 161280 - 108847 * n6 / 3991680,
            20648693 * n6 / 638668800,
        )

    def forward(self, lon: float, lat: float) -> Point:
        """Geographic degrees -> projected metres (easting, northing)."""
        phi = math.radians(lat)
        lam = math.radians(lon) - self.lon0
        e = self.e
        sin_phi = math.sin(phi)
        t = math.sinh(math.atanh(sin_phi) - e * math.atanh(e * sin_phi))
        xi_p = math.atan2(t, math.cos(lam))
        eta_p = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
        xi, eta = xi_p, eta_p
        for j, a in enumerate(self.alpha, start=1):
            xi += a * math.sin(2 * j * xi_p) * math.cosh(2 * j * eta_p)
            eta += a * math.cos(2 * j * xi_p) * math.sinh(2 * j * eta_p)
        return (self.fe + self.k0 * self.A * eta, self.fn + self.k0 * self.A * xi)

    def inverse(self, x: float, y: float) -> Point:
        """Projected metres -> geographic degrees (lon, lat)."""
        xi = (y - self.fn) / (self.k0 * self.A)
        eta = (x - self.fe) / (self.k0 * self.A)
        xi_p, eta_p = xi, eta
        for j, b in enumerate(self.beta, start=1):
            xi_p -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
            eta_p -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
        chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
        lam = math.atan2(math.sinh(eta_p), math.cos(xi_p))
        # conformal latitude -> geodetic latitude (Newton on tau = tan(phi))
        e, e2 = self.e, self.ell.e2
        tau_p = math.tan(chi)
        tau = tau_p
        for _ in range(8):
            sigma = math.sinh(e * math.atanh(e * tau / math.sqrt(1 + tau * tau)))
            tau_i = tau * math.sqrt(1 + sigma * sigma) - sigma * math.sqrt(1 + tau * tau)
            d = ((tau_p - tau_i) / math.sqrt(1 + tau_i * tau_i)
                 * (1 + (1 - e2) * tau * tau) / ((1 - e2) * math.sqrt(1 + tau * tau)))
            tau += d
            if abs(d) < 1e-14:
                break
        return (math.degrees(lam + self.lon0), math.degrees(math.atan(tau)))


UTM32 = TransverseMercator(GRS80, 9.0, 0.9996, 500000.0)
GK2 = TransverseMercator(BESSEL, 6.0, 1.0, 2500000.0)
GK3 = TransverseMercator(BESSEL, 9.0, 1.0, 3500000.0)
GK4 = TransverseMercator(BESSEL, 12.0, 1.0, 4500000.0)

# --------------------------------------------------------------------------
# Datum shift DHDN <-> ETRS89 (7-parameter Helmert, position vector)
# --------------------------------------------------------------------------

# EPSG:1776 "DHDN to WGS 84 (2)", nationwide parameters, ~1-3 m.
_DHDN_TO_ETRS89 = (598.1, 73.7, 418.2, 0.202, 0.045, -2.455, 6.7)


def _geodetic_to_ecef(lon: float, lat: float, ell: Ellipsoid) -> tuple[float, float, float]:
    phi, lam = math.radians(lat), math.radians(lon)
    n = ell.a / math.sqrt(1 - ell.e2 * math.sin(phi) ** 2)
    return (n * math.cos(phi) * math.cos(lam),
            n * math.cos(phi) * math.sin(lam),
            n * (1 - ell.e2) * math.sin(phi))


def _ecef_to_geodetic(x: float, y: float, z: float, ell: Ellipsoid) -> Point:
    p = math.hypot(x, y)
    lam = math.atan2(y, x)
    phi = math.atan2(z, p * (1 - ell.e2))
    for _ in range(6):
        n = ell.a / math.sqrt(1 - ell.e2 * math.sin(phi) ** 2)
        h = p / math.cos(phi) - n
        phi = math.atan2(z, p * (1 - ell.e2 * n / (n + h)))
    return (math.degrees(lam), math.degrees(phi))


def _helmert(xyz: tuple[float, float, float], params: Sequence[float],
             inverse: bool = False) -> tuple[float, float, float]:
    tx, ty, tz, rx, ry, rz, s = params
    sign = -1.0 if inverse else 1.0
    k = math.pi / (180 * 3600)
    rx, ry, rz = sign * rx * k, sign * ry * k, sign * rz * k
    tx, ty, tz, s = sign * tx, sign * ty, sign * tz, sign * s * 1e-6
    x, y, z = xyz
    if inverse:  # remove translation first, then rotate back
        x, y, z = x + tx, y + ty, z + tz
        return ((1 + s) * (x - rz * y + ry * z),
                (1 + s) * (rz * x + y - rx * z),
                (1 + s) * (-ry * x + rx * y + z))
    return (tx + (1 + s) * (x - rz * y + ry * z),
            ty + (1 + s) * (rz * x + y - rx * z),
            tz + (1 + s) * (-ry * x + rx * y + z))


def dhdn_to_etrs89(lon: float, lat: float) -> Point:
    xyz = _geodetic_to_ecef(lon, lat, BESSEL)
    return _ecef_to_geodetic(*_helmert(xyz, _DHDN_TO_ETRS89), GRS80)


def etrs89_to_dhdn(lon: float, lat: float) -> Point:
    xyz = _geodetic_to_ecef(lon, lat, GRS80)
    return _ecef_to_geodetic(*_helmert(xyz, _DHDN_TO_ETRS89, inverse=True), BESSEL)


# --------------------------------------------------------------------------
# CRS handling: everything is converted to/from EPSG:25832
# --------------------------------------------------------------------------

_R_WEB = 6378137.0


def _to_lonlat(code: int) -> Callable[[float, float], Point]:
    if code in (4326, 4258):
        return lambda x, y: (x, y)
    if code == 25832:
        return UTM32.inverse
    if code == 4647:  # UTM 32 with zone prefix in the easting
        return lambda x, y: UTM32.inverse(x - 32_000_000.0, y)
    if code == 3857:
        return lambda x, y: (math.degrees(x / _R_WEB),
                             math.degrees(math.atan(math.sinh(y / _R_WEB))))
    gk = {31466: GK2, 31467: GK3, 31468: GK4}.get(code)
    if gk is not None:
        return lambda x, y: dhdn_to_etrs89(*gk.inverse(x, y))
    raise ValueError(f"Koordinatensystem EPSG:{code} wird nicht unterstützt "
                     "(unterstützt: 4326, 4258, 3857, 25832, 4647, 31466, 31467, 31468)")


def _from_lonlat(code: int) -> Callable[[float, float], Point]:
    if code in (4326, 4258):
        return lambda x, y: (x, y)
    if code == 25832:
        return UTM32.forward
    if code == 4647:
        return lambda lon, lat: (lambda e, n: (e + 32_000_000.0, n))(*UTM32.forward(lon, lat))
    if code == 3857:
        return lambda lon, lat: (math.radians(lon) * _R_WEB,
                                 math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * _R_WEB)
    gk = {31466: GK2, 31467: GK3, 31468: GK4}.get(code)
    if gk is not None:
        return lambda lon, lat: gk.forward(*etrs89_to_dhdn(lon, lat))
    raise ValueError(f"Koordinatensystem EPSG:{code} wird nicht unterstützt")


def parse_crs(crs: str | int | None) -> int | None:
    """'EPSG:25832', 'urn:ogc:def:crs:EPSG::4326', 25832, 'CRS84' -> int code."""
    if crs is None or crs == "":
        return None
    if isinstance(crs, int):
        return crs
    s = str(crs).strip()
    if s.upper().endswith("CRS84"):
        return 4326
    m = re.search(r"(\d{4,5})\s*$", s)
    if not m:
        raise ValueError(f"Unbekannte Koordinatensystem-Angabe: {crs!r}")
    return int(m.group(1))


def transformer(src: int, dst: int) -> Callable[[float, float], Point]:
    """Return a function mapping (x, y) from EPSG:src to EPSG:dst."""
    if src == dst:
        return lambda x, y: (x, y)
    to_ll, from_ll = _to_lonlat(src), _from_lonlat(dst)
    return lambda x, y: from_ll(*to_ll(x, y))


def guess_crs(x: float, y: float) -> int:
    """Guess the CRS of a coordinate pair from its value range."""
    if -180 <= x <= 180 and -90 <= y <= 90:
        return 4326
    if 100_000 <= x <= 900_000 and 5_000_000 <= y <= 6_500_000:
        return 25832
    if 32_100_000 <= x <= 32_900_000:
        return 4647
    if 2_000_000 <= x < 5_000_000 and 5_000_000 <= y <= 6_500_000:
        return 31464 + int(x // 1_000_000)  # zone 2 -> 31466 ...
    raise ValueError(f"Koordinaten ({x}, {y}) passen zu keinem bekannten System; "
                     "bitte das Koordinatensystem angeben (z. B. crs='EPSG:25832').")


# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def __post_init__(self):
        if self.minx > self.maxx or self.miny > self.maxy:
            raise ValueError(f"Ungültige Bounding Box: {self}")

    def intersects(self, o: BBox) -> bool:
        return not (o.minx > self.maxx or o.maxx < self.minx
                    or o.miny > self.maxy or o.maxy < self.miny)

    def buffer(self, d: float) -> BBox:
        return BBox(self.minx - d, self.miny - d, self.maxx + d, self.maxy + d)

    @property
    def width(self) -> float:
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        return self.maxy - self.miny

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return ((self.minx + self.maxx) / 2, (self.miny + self.maxy) / 2)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.minx, self.miny, self.maxx, self.maxy)


def _bbox_of(points: Iterable[Point]) -> BBox | None:
    xs, ys = [], []
    for x, y in points:
        xs.append(x)
        ys.append(y)
    if not xs:
        return None
    return BBox(min(xs), min(ys), max(xs), max(ys))


def _densify(ring: Sequence[Point], step: float) -> Ring:
    out: Ring = []
    n = len(ring)
    for i in range(n - 1):
        (x1, y1), (x2, y2) = ring[i], ring[i + 1]
        out.append((x1, y1))
        d = math.hypot(x2 - x1, y2 - y1)
        k = int(d // step)
        for j in range(1, k + 1):
            t = j / (k + 1)
            out.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
    if ring:
        out.append(tuple(ring[-1]))  # type: ignore[arg-type]
    return out


class Shape:
    """A (multi)polygon and/or a set of lines/points in one CRS.

    ``rings`` hold polygon boundaries (outer rings and holes, evaluated with
    the even-odd rule), ``lines`` hold non-areal parts (line strings; a point
    is a line of length zero).
    """

    def __init__(self, rings: Iterable[Sequence[Point]] = (),
                 lines: Iterable[Sequence[Point]] = (), crs: int = 25832):
        self.rings: list[Ring] = []
        for r in rings:
            r = [(float(x), float(y)) for x, y, *_ in r]
            if len(r) < 3:
                continue
            if r[0] != r[-1]:
                r.append(r[0])
            self.rings.append(r)
        self.lines: list[Ring] = [[(float(x), float(y)) for x, y, *_ in ln] for ln in lines if ln]
        self.crs = crs
        bb = _bbox_of(p for part in self.rings + self.lines for p in part)
        if bb is None:
            raise ValueError("Leere Geometrie")
        self.bbox: BBox = bb

    # -- constructors ------------------------------------------------------
    @classmethod
    def from_bbox(cls, minx: float, miny: float, maxx: float, maxy: float,
                  crs: int = 25832) -> Shape:
        b = BBox(minx, miny, maxx, maxy)
        if b.width == 0 or b.height == 0:
            return cls(lines=[[(minx, miny), (maxx, maxy)]], crs=crs)
        return cls(rings=[[(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]], crs=crs)

    @classmethod
    def circle(cls, x: float, y: float, radius: float, n: int = 64,
               crs: int = 25832) -> Shape:
        if radius <= 0:
            return cls(lines=[[(x, y), (x, y)]], crs=crs)
        # circumscribed polygon so the circle is fully covered
        r = radius / math.cos(math.pi / n)
        pts = [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n))
               for i in range(n)]
        return cls(rings=[pts], crs=crs)

    @classmethod
    def from_geojson(cls, obj: dict, crs: int | None = None) -> Shape:
        """Build a shape from a GeoJSON geometry, Feature or FeatureCollection."""
        rings: list[Ring] = []
        lines: list[Ring] = []
        if crs is None:
            name = ((obj.get("crs") or {}).get("properties") or {}).get("name")
            crs = parse_crs(name) if name else None

        def walk(g: dict) -> None:
            t = g.get("type")
            if t == "FeatureCollection":
                for f in g.get("features") or []:
                    walk(f)
            elif t == "Feature":
                if g.get("geometry"):
                    walk(g["geometry"])
            elif t == "GeometryCollection":
                for gg in g.get("geometries") or []:
                    walk(gg)
            elif t == "Polygon":
                rings.extend(g["coordinates"])
            elif t == "MultiPolygon":
                for poly in g["coordinates"]:
                    rings.extend(poly)
            elif t == "LineString":
                lines.append(g["coordinates"])
            elif t == "MultiLineString":
                lines.extend(g["coordinates"])
            elif t == "Point":
                lines.append([g["coordinates"], g["coordinates"]])
            elif t == "MultiPoint":
                lines.extend([p, p] for p in g["coordinates"])
            else:
                raise ValueError(f"GeoJSON-Typ {t!r} wird nicht unterstützt")

        walk(obj)
        if not rings and not lines:
            raise ValueError("GeoJSON enthält keine Geometrie")
        if crs is None:
            x, y = (rings or lines)[0][0][:2]
            crs = 4326 if (-180 <= x <= 180 and -90 <= y <= 90) else guess_crs(x, y)
        return cls(rings=rings, lines=lines, crs=crs)

    # -- operations --------------------------------------------------------
    def parts(self) -> Iterator[Ring]:
        yield from self.rings
        yield from self.lines

    def transform(self, dst: int, densify: float | None = None) -> Shape:
        """Reproject. ``densify`` inserts vertices (in source units) first so
        straight edges in the source CRS stay faithful after projection."""
        if dst == self.crs:
            return self
        if densify is None:
            densify = 0.01 if self.crs in (4326, 4258) else 1000.0
        fn = transformer(self.crs, dst)
        rings = [[fn(x, y) for x, y in _densify(r, densify)] for r in self.rings]
        lines = [[fn(x, y) for x, y in _densify(ln, densify)] for ln in self.lines]
        return Shape(rings=rings, lines=lines, crs=dst)

    @property
    def area(self) -> float:
        """Area with the even-odd rule (rings inside an odd number of other
        rings are holes)."""
        total = 0.0
        for i, r in enumerate(self.rings):
            a = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:]))) / 2
            depth = sum(1 for j, o in enumerate(self.rings) if j != i and _point_in_ring(r[0], o))
            total += -a if depth % 2 else a
        return total

    def interior_points(self) -> list[Point]:
        """One point strictly inside the area near every ring (even-odd)."""
        pts: list[Point] = []
        for r in self.rings:
            ys = [y for _, y in r]
            xs = [x for x, _ in r]
            y = (min(ys) + max(ys)) / 2 + (max(ys) - min(ys)) * 1.234567e-7
            cr = _ring_crossings(self.rings, y)
            best = None
            for x0, x1 in zip(cr[0::2], cr[1::2]):
                if x1 < min(xs) or x0 > max(xs) or x1 <= x0:
                    continue
                if best is None or x1 - x0 > best[1] - best[0]:
                    best = (x0, x1)
            if best:
                pts.append(((best[0] + best[1]) / 2, y))
        return pts

    def centroid_lonlat(self) -> Point:
        cx, cy = self.bbox.center
        return transformer(self.crs, 4326)(cx, cy)

    def to_geojson(self) -> dict:
        """GeoJSON geometry in the shape's CRS (rings as separate polygons)."""
        geoms = []
        if self.rings:
            geoms.append({"type": "MultiPolygon", "coordinates": [[r] for r in self.rings]})
        if self.lines:
            geoms.append({"type": "MultiLineString", "coordinates": self.lines})
        if len(geoms) == 1:
            return geoms[0]
        return {"type": "GeometryCollection", "geometries": geoms}

    def __repr__(self) -> str:
        return (f"Shape(EPSG:{self.crs}, {len(self.rings)} Ringe, {len(self.lines)} Linien, "
                f"bbox={tuple(round(v, 3) for v in self.bbox.as_tuple())})")


def _point_in_ring(p: Point, ring: Ring) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def segment_intersects_rect(x1: float, y1: float, x2: float, y2: float,
                            minx: float, miny: float, maxx: float, maxy: float,
                            strict: bool = False) -> bool:
    """Liang-Barsky clipping test (also works for zero-length segments).

    ``strict=True`` asks whether the segment passes through the *open*
    interior, i.e. merely touching the border does not count."""
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - minx), (dx, maxx - x1), (-dy, y1 - miny), (dy, maxy - y1)):
        if p == 0:
            if q < 0 or (strict and q == 0):
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 < t1 if strict else t0 <= t1


def _orient(ax, ay, bx, by, cx, cy) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    d1 = _orient(*c, *d, *a)
    d2 = _orient(*c, *d, *b)
    d3 = _orient(*a, *b, *c)
    d4 = _orient(*a, *b, *d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
        return True

    def on_seg(p, q, r) -> bool:  # r on segment pq (given collinear)
        return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
                and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))

    if d1 == 0 and on_seg(c, d, a):
        return True
    if d2 == 0 and on_seg(c, d, b):
        return True
    if d3 == 0 and on_seg(a, b, c):
        return True
    if d4 == 0 and on_seg(a, b, d):
        return True
    return False


def segments_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True if the segments cross transversally (touching does not count)."""
    d1 = _orient(*c, *d, *a)
    d2 = _orient(*c, *d, *b)
    d3 = _orient(*a, *b, *c)
    d4 = _orient(*a, *b, *d)
    return d1 * d2 < 0 and d3 * d4 < 0


def _ring_crossings(rings: list[Ring], y: float) -> list[float]:
    xs = []
    for r in rings:
        for (x1, y1), (x2, y2) in zip(r, r[1:]):
            if (y1 > y) != (y2 > y):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return sorted(xs)


class ShapeIndex:
    """Fast rectangle/shape intersection tests for one :class:`Shape`.

    Edges are bucketed into a regular grid; "is the rectangle centre inside
    the polygon" is answered with cached scan-line crossings. A rectangle
    intersects an areal shape iff its centre lies inside it or one of the
    shape's edges passes through the rectangle - both checks touch only the
    edges near the rectangle.
    """

    def __init__(self, shape: Shape, cell: float | None = None):
        self.shape = shape
        bb = shape.bbox
        if cell is None:
            cell = max(bb.width, bb.height) / 64 or 1.0
        self.cell = cell
        self.edges: list[tuple[float, float, float, float]] = []
        self.areal_edges: list[tuple[float, float, float, float]] = []
        for r in shape.rings:
            for (x1, y1), (x2, y2) in zip(r, r[1:]):
                self.edges.append((x1, y1, x2, y2))
                self.areal_edges.append((x1, y1, x2, y2))
        self.n_areal = len(self.edges)
        for ln in shape.lines:
            if len(ln) == 1:
                ln = [ln[0], ln[0]]
            for (x1, y1), (x2, y2) in zip(ln, ln[1:]):
                self.edges.append((x1, y1, x2, y2))
        self.buckets: dict[tuple[int, int], list[int]] = {}
        for i, (x1, y1, x2, y2) in enumerate(self.edges):
            for key in self._cells(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)):
                self.buckets.setdefault(key, []).append(i)
        # rows of areal edges for scan lines
        self.rows: dict[int, list[int]] = {}
        for i, (_x1, y1, _x2, y2) in enumerate(self.areal_edges):
            r0 = math.floor((min(y1, y2) - bb.miny) / cell)
            r1 = math.floor((max(y1, y2) - bb.miny) / cell)
            for r in range(r0, r1 + 1):
                self.rows.setdefault(r, []).append(i)
        self._scan_cache: dict[float, list[float]] = {}

    def _cells(self, minx, miny, maxx, maxy) -> Iterator[tuple[int, int]]:
        bb, c = self.shape.bbox, self.cell
        i0 = math.floor((minx - bb.minx) / c)
        i1 = math.floor((maxx - bb.minx) / c)
        j0 = math.floor((miny - bb.miny) / c)
        j1 = math.floor((maxy - bb.miny) / c)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield (i, j)

    def _crossings(self, y: float) -> list[float]:
        xs = self._scan_cache.get(y)
        if xs is None:
            row = math.floor((y - self.shape.bbox.miny) / self.cell)
            xs = []
            for i in self.rows.get(row, ()):
                x1, y1, x2, y2 = self.areal_edges[i]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            self._scan_cache[y] = xs
        return xs

    def contains_point(self, x: float, y: float) -> bool:
        if not self.areal_edges:
            return False
        bb = self.shape.bbox
        if not (bb.minx <= x <= bb.maxx and bb.miny <= y <= bb.maxy):
            return False
        xs = self._crossings(y)
        # number of crossings left of x
        lo, hi = 0, len(xs)
        while lo < hi:
            mid = (lo + hi) // 2
            if xs[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        return lo % 2 == 1

    def intersects_rect(self, minx: float, miny: float, maxx: float, maxy: float) -> bool:
        """Does the rectangle overlap the shape? For areas this means a
        common area > 0 (touching along a border is not enough); lines and
        points count when they touch the closed rectangle."""
        bb = self.shape.bbox
        if minx > bb.maxx or maxx < bb.minx or miny > bb.maxy or maxy < bb.miny:
            return False
        if self.contains_point((minx + maxx) / 2, (miny + maxy) / 2):
            return True
        seen: set[int] = set()
        for key in self._cells(max(minx, bb.minx), max(miny, bb.miny),
                               min(maxx, bb.maxx), min(maxy, bb.maxy)):
            for i in self.buckets.get(key, ()):
                if i in seen:
                    continue
                seen.add(i)
                if segment_intersects_rect(*self.edges[i], minx, miny, maxx, maxy,
                                           strict=i < self.n_areal):
                    return True
        return False

    def _edge_candidates(self, x1, y1, x2, y2) -> Iterator[int]:
        bb = self.shape.bbox
        ex0, ey0, ex1, ey1 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if ex0 > bb.maxx or ex1 < bb.minx or ey0 > bb.maxy or ey1 < bb.miny:
            return
        seen: set[int] = set()
        for key in self._cells(max(ex0, bb.minx), max(ey0, bb.miny),
                               min(ex1, bb.maxx), min(ey1, bb.maxy)):
            for i in self.buckets.get(key, ()):
                if i not in seen:
                    seen.add(i)
                    yield i

    def intersects_shape(self, other: Shape) -> bool:
        """Does ``other`` (same CRS) overlap this shape? Two areas must share
        an area > 0; shared borders alone do not count. Lines and points
        count when they touch."""
        if not self.shape.bbox.intersects(other.bbox):
            return False
        oidx = ShapeIndex(other)
        for x, y in other.interior_points():
            if self.contains_point(x, y):
                return True
        for x, y in self.shape.interior_points():
            if oidx.contains_point(x, y):
                return True
        for part in other.lines:
            if self.contains_point(*part[0]):
                return True
        for part in self.shape.lines:
            if oidx.contains_point(*part[0]):
                return True
        for j, (x1, y1, x2, y2) in enumerate(oidx.edges):
            areal_o = j < oidx.n_areal
            for i in self._edge_candidates(x1, y1, x2, y2):
                ax, ay, bx, by = self.edges[i]
                if areal_o and i < self.n_areal:
                    if segments_cross((x1, y1), (x2, y2), (ax, ay), (bx, by)):
                        return True
                elif segments_intersect((x1, y1), (x2, y2), (ax, ay), (bx, by)):
                    return True
        return False
