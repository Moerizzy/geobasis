"""Administrative units (municipalities, districts, regions) for any state.

A :class:`BoundaryProvider` knows two things about a state: a light-weight
list of its units (name, official key, extent) and how to fetch the exact
boundary of one unit. Name lookup, typo suggestions and "which districts
touch this area?" are implemented here once for all states.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from .area import Area
from .geo import BBox, Shape, ShapeIndex

LEVEL_NAMES = {"gemeinde": "Gemeinde", "kreis": "Kreis", "regbez": "Regierungsbezirk"}
# length of the AGS prefix that identifies a unit of this level
AGS_PREFIX = {"kreis": 5, "regbez": 3}

_PREFIXES = ("kreisfreie stadt ", "landkreis ", "kreis ", "stadt ", "gemeinde ", "region ",
             "samtgemeinde ", "regierungsbezirk ", "regbez ", "rb ")


@dataclass(frozen=True)
class Unit:
    level: str
    ags: str  # 8-digit official key ("Amtlicher Gemeindeschlüssel"), e.g. 05515000
    name: str
    bbox: BBox
    bez: str = ""  # official type, e.g. "Landkreis", "Kreisfreie Stadt"
    land: str = ""

    @property
    def label(self) -> str:
        kind = self.bez or LEVEL_NAMES[self.level]
        return f"{kind} {self.name} ({self.ags})"


def norm(s: str) -> str:
    """Normalise a place name: lower case, umlauts as ae/oe/ue, no punctuation."""
    s = s.lower().strip()
    s = re.sub(r"\ba\.\s*d\.\s*", "an der ", s)
    s = re.sub(r"\bi\.\s*", "im ", s)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def plain(s: str) -> str:
    """Like :func:`norm` but umlauts lose their 'e' (Münster/Muenster -> munster)."""
    s = norm(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    return s


_providers: list[BoundaryProvider] = []


def clear_caches() -> None:
    """Forget all cached unit lists and boundaries (used by tests)."""
    for p in _providers:
        p._units.clear()
        p._geoms.clear()


class BoundaryProvider:
    """Base class; subclasses implement ``_fetch_units`` and ``_fetch_geometry``."""

    land = ""
    levels: tuple[str, ...] = ("gemeinde", "kreis")

    def __init__(self) -> None:
        self._units: dict[str, list[Unit]] = {}
        self._geoms: dict[tuple[str, str], Shape] = {}
        _providers.append(self)

    # -- to implement --------------------------------------------------------
    def _fetch_units(self, level: str) -> list[Unit]:  # pragma: no cover
        raise NotImplementedError

    def _fetch_geometry(self, level: str, ags: str) -> Shape:  # pragma: no cover
        raise NotImplementedError

    # -- generic ----------------------------------------------------------------
    def _check_level(self, level: str) -> None:
        if level not in LEVEL_NAMES:
            raise ValueError(f"Ebene {level!r} unbekannt (gemeinde, kreis, regbez)")
        if level not in self.levels:
            raise LookupError(f"{LEVEL_NAMES[level]}e gibt es hier nicht als Gebietsangabe "
                              f"(verfügbar: {', '.join(self.levels)})")

    def units(self, level: str) -> list[Unit]:
        self._check_level(level)
        if level not in self._units:
            self._units[level] = sorted(self._fetch_units(level), key=lambda u: (norm(u.name), u.ags))
        return self._units[level]

    def geometry(self, level: str, ags: str) -> Shape:
        k = (level, ags)
        if k not in self._geoms:
            self._geoms[k] = self._fetch_geometry(level, ags)
        return self._geoms[k]

    def lookup(self, level: str, query: str) -> Unit:
        """Find one unit by name or key. Raises ``LookupError`` with suggestions."""
        return self.lookup_ranked(level, query)[0]

    def lookup_ranked(self, level: str, query: str) -> tuple[Unit, int]:
        """Like :meth:`lookup`, plus the match quality (0 = exact key or name,
        higher = looser match). Used to rank hits across states."""
        cands = self.units(level)
        q = str(query).strip()
        digits = re.sub(r"\s", "", q)
        if digits.isdigit():
            hits = [u for u in cands if u.ags == digits.ljust(8, "0") or u.ags == digits]
            if not hits:
                hits = [u for u in cands if u.ags.startswith(digits)]
            if len(hits) == 1:
                return hits[0], 0
            if hits:
                raise LookupError(self._ambiguous(level, q, hits))
            raise LookupError(f"Keine {LEVEL_NAMES[level]} mit Schlüssel {q} gefunden.")
        nq = norm(q)
        kind = ""
        for p in _PREFIXES:
            if nq.startswith(p) and len(nq) > len(p):
                kind, nq = p.strip(), nq[len(p):]
                break
        rank = 0
        for fn in (norm, plain):  # "Muenster" first, then "Munster"
            nn = nq if fn is norm else plain(nq)
            for test in (lambda n, q=nn: n == q, lambda n, q=nn: n.startswith(q),
                         lambda n, q=nn: q in n.split(" "), lambda n, q=nn: q in n):
                hits = [u for u in cands if test(fn(u.name))]
                if len(hits) > 1 and kind:  # "Landkreis Osnabrück" vs. "Stadt Osnabrück"
                    typed = [u for u in hits if kind in norm(u.bez)]
                    hits = typed or hits
                if len(hits) == 1:
                    return hits[0], rank
                if len(hits) > 1:
                    raise LookupError(self._ambiguous(level, q, hits))
                rank += 1
        names = {norm(u.name): u.name for u in cands}
        close = difflib.get_close_matches(nq, list(names), n=5, cutoff=0.6)
        hint = f" Meinten Sie: {', '.join(names[c] for c in close)}?" if close else ""
        raise LookupError(f"{LEVEL_NAMES[level]} {q!r} nicht gefunden.{hint}")

    def _ambiguous(self, level: str, q: str, hits: list[Unit]) -> str:
        kreise: dict[str, str] = {}
        if level == "gemeinde" and "kreis" in self.levels:
            try:
                kreise = {u.ags[:5]: u.name for u in self.units("kreis")}
            except Exception:  # noqa: BLE001 - only used to make the message nicer
                kreise = {}
        opts = ", ".join(u.label[:-1] + (f", {kreise[u.ags[:5]]})" if u.ags[:5] in kreise
                                         and kreise[u.ags[:5]] != u.name else ")")
                         for u in hits[:10])
        return (f"{LEVEL_NAMES[level]} {q!r} ist mehrdeutig: {opts}. "
                "Bitte genauer angeben oder den Schlüssel verwenden.")

    def area_of(self, unit: Unit) -> Area:
        return Area(self.geometry(unit.level, unit.ags), unit.label, ags=unit.ags, level=unit.level)

    def area(self, level: str, query: str) -> Area:
        return self.area_of(self.lookup(level, query))

    def search(self, level: str, text: str | None = None) -> list[Unit]:
        units = self.units(level)
        if not text:
            return units
        q = norm(text)
        return [u for u in units if q in norm(u.name) or u.ags.startswith(text.strip())]

    def units_for(self, level: str, a: Area) -> list[Unit]:
        """Units of ``level`` that share an area with ``a``."""
        all_units = self.units(level)
        if a.ags and a.level:
            if a.level == level:
                return [u for u in all_units if u.ags == a.ags]
            n = AGS_PREFIX.get(level)
            if n and (a.level == "gemeinde" or (a.level == "kreis" and level == "regbez")):
                return [u for u in all_units if u.ags[:n] == a.ags[:n]]
            if a.level == "regbez" and level == "kreis":
                return [u for u in all_units if u.ags[:3] == a.ags[:3]]
        cands = [u for u in all_units if u.bbox.buffer(500).intersects(a.shape.bbox)]
        return [u for u in cands if ShapeIndex(self.geometry(level, u.ags)).intersects_shape(a.shape)]


def bbox_of_geometry(geom: dict) -> BBox:
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
