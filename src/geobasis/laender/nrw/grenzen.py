"""Administrative units of NRW (municipalities, districts, regions).

Names and rough extents come from the generalised DVG2 layer (one cached
request per level); the exact boundary of a selected unit is fetched from
the detailed DVG1 layer with a key filter. Both via the official WFS
https://www.wfs.nrw.de/geobasis/wfs_nw_dvg (dl-de/zero-2-0).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass

from ... import http
from ...area import Area
from ...geo import BBox, Shape, ShapeIndex

WFS = "https://www.wfs.nrw.de/geobasis/wfs_nw_dvg"
LEVELS = {"gemeinde": "gem", "kreis": "krs", "regbez": "rbz"}
LEVEL_NAMES = {"gemeinde": "Gemeinde", "kreis": "Kreis", "regbez": "Regierungsbezirk"}
_TTL = 30 * 24 * 3600  # boundaries change rarely


@dataclass(frozen=True)
class Unit:
    level: str
    ags: str  # 8-digit key ("Kennziffer"), e.g. 05515000
    name: str
    bbox: BBox

    @property
    def label(self) -> str:
        return f"{LEVEL_NAMES[self.level]} {self.name} ({self.ags})"


def _wfs_url(typename: str, flt: str | None = None) -> str:
    q = {"SERVICE": "WFS", "REQUEST": "GetFeature", "VERSION": "2.0.0",
         "TYPENAMES": f"dvg:{typename}", "OUTPUTFORMAT": "application/json; subtype=geojson"}
    if flt:
        q["FILTER"] = flt
    return WFS + "?" + urllib.parse.urlencode(q)


def _bbox_of_geometry(geom: dict) -> BBox:
    xs, ys = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for cc in c:
                walk(cc)

    walk(geom["coordinates"])
    return BBox(min(xs), min(ys), max(xs), max(ys))


_units_cache: dict[str, list[Unit]] = {}


def units(level: str) -> list[Unit]:
    """All units of a level, sorted by name."""
    if level not in LEVELS:
        raise ValueError(f"Ebene {level!r} unbekannt (gemeinde, kreis, regbez)")
    if level not in _units_cache:
        d = http.fetch_json(_wfs_url(f"nw_dvg2_{LEVELS[level]}"), ttl=_TTL)
        out = [Unit(level, f["properties"]["KN"], f["properties"]["GN"],
                    _bbox_of_geometry(f["geometry"]))
               for f in d.get("features") or [] if f.get("geometry")]
        _units_cache[level] = sorted(out, key=lambda u: _norm(u.name))
    return _units_cache[level]


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\ba\.\s*d\.\s*", "an der ", s)
    s = re.sub(r"\bi\.\s*", "im ", s)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _plain(s: str) -> str:
    """Like :func:`_norm` but umlauts lose their 'e' (Münster/Muenster -> munster)."""
    s = _norm(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    return s


_PREFIXES = ("kreis ", "landkreis ", "stadt ", "kreisfreie stadt ", "gemeinde ",
             "regierungsbezirk ", "regbez ", "rb ")


def lookup(level: str, query: str) -> Unit:
    """Find one unit by name or key. Raises ``LookupError`` with suggestions."""
    cands = units(level)
    q = str(query).strip()
    digits = re.sub(r"\s", "", q)
    if digits.isdigit():
        if len(digits) <= 8:
            hits = [u for u in cands if u.ags == digits.ljust(8, "0") or u.ags == digits]
            if not hits:
                hits = [u for u in cands if u.ags.startswith(digits)]
            if len(hits) == 1:
                return hits[0]
            if hits:
                raise LookupError(_ambiguous(level, q, hits))
        raise LookupError(f"Keine {LEVEL_NAMES[level]} mit Schlüssel {q} in NRW gefunden.")
    nq = _norm(q)
    for p in _PREFIXES:
        if nq.startswith(p) and len(nq) > len(p):
            stripped = nq[len(p):]
            if any(_norm(u.name) == stripped for u in cands):
                nq = stripped
            break
    for norm in (_norm, _plain):  # "Muenster" first, then "Munster"
        nn = nq if norm is _norm else _plain(nq)
        for test in (lambda n, q=nn: n == q, lambda n, q=nn: n.startswith(q),
                     lambda n, q=nn: q in n.split(" "), lambda n, q=nn: q in n):
            hits = [u for u in cands if test(norm(u.name))]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                raise LookupError(_ambiguous(level, q, hits))
    names = {_norm(u.name): u.name for u in cands}
    close = difflib.get_close_matches(nq, list(names), n=5, cutoff=0.6)
    hint = f" Meinten Sie: {', '.join(names[c] for c in close)}?" if close else ""
    raise LookupError(f"{LEVEL_NAMES[level]} {q!r} nicht gefunden.{hint}")


def _ambiguous(level: str, q: str, hits: list[Unit]) -> str:
    opts = ", ".join(f"{u.name} ({u.ags})" for u in hits[:10])
    return (f"{LEVEL_NAMES[level]} {q!r} ist mehrdeutig: {opts}. "
            "Bitte genauer angeben oder den Schlüssel verwenden.")


_geom_cache: dict[tuple[str, str], Shape] = {}


def geometry(level: str, ags: str) -> Shape:
    """Exact (DVG1) boundary of a unit in EPSG:25832."""
    k = (level, ags)
    if k not in _geom_cache:
        flt = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
               f"<fes:ValueReference>KN</fes:ValueReference><fes:Literal>{ags}</fes:Literal>"
               "</fes:PropertyIsEqualTo></fes:Filter>")
        d = http.fetch_json(_wfs_url(f"nw_dvg1_{LEVELS[level]}", flt), ttl=_TTL)
        if not d.get("features"):
            raise LookupError(f"Keine Geometrie für {ags} ({level}) gefunden")
        _geom_cache[k] = Shape.from_geojson(d, crs=25832)
    return _geom_cache[k]


def area(level: str, query: str) -> Area:
    u = lookup(level, query)
    return Area(geometry(level, u.ags), u.label, ags=u.ags, level=level)


def units_for(level: str, a: Area) -> list[Unit]:
    """Units of ``level`` ('kreis' or 'regbez') that touch the area."""
    all_units = units(level)
    if a.ags and a.level:
        if a.level == level:
            return [u for u in all_units if u.ags == a.ags]
        prefix = {"kreis": 5, "regbez": 3}[level]
        if a.level == "gemeinde" or (a.level == "kreis" and level == "regbez"):
            return [u for u in all_units if u.ags[:prefix] == a.ags[:prefix]]
        if a.level == "regbez" and level == "kreis":
            return [u for u in all_units if u.ags[:3] == a.ags[:3]]
    cands = [u for u in all_units if u.bbox.buffer(500).intersects(a.shape.bbox)]
    out = []
    for u in cands:
        if ShapeIndex(geometry(level, u.ags)).intersects_shape(a.shape):
            out.append(u)
    return out
